# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging

from vitrage.common.constants import EdgeLabels
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EventAction
from vitrage.common.constants import SynchronizerProperties as SyncProps
from vitrage.common.constants import SyncMode
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common.exception import VitrageTransformerError
import vitrage.graph.utils as graph_utils
from vitrage.synchronizer.plugins.base.resource.transformer import \
    BaseResourceTransformer
from vitrage.synchronizer.plugins.nova.host import NOVA_HOST_PLUGIN
from vitrage.synchronizer.plugins.nova.instance import NOVA_INSTANCE_PLUGIN
from vitrage.synchronizer.plugins import transformer_base as tbase
from vitrage.synchronizer.plugins.transformer_base import extract_field_value
from vitrage.synchronizer.plugins.transformer_base import Neighbor

LOG = logging.getLogger(__name__)


class InstanceTransformer(BaseResourceTransformer):

    # Event types which need to refer them differently
    UPDATE_EVENT_TYPES = {
        'compute.instance.delete.end': EventAction.DELETE_ENTITY,
    }

    def __init__(self, transformers):
        super(InstanceTransformer, self).__init__(transformers)

    def _create_snapshot_entity_vertex(self, entity_event):

        name = extract_field_value(entity_event, 'name')
        entity_id = extract_field_value(entity_event, 'id')
        state = extract_field_value(entity_event, 'status')

        return self._create_vertex(entity_event, name, entity_id, state)

    def _create_update_entity_vertex(self, entity_event):

        name = extract_field_value(entity_event, 'hostname')
        entity_id = extract_field_value(entity_event, 'instance_id')
        state = extract_field_value(entity_event, 'state')

        return self._create_vertex(entity_event, name, entity_id, state)

    def _create_vertex(self, entity_event, name, entity_id, state):

        project = extract_field_value(entity_event, 'tenant_id')

        metadata = {
            VProps.NAME: name,
            VProps.IS_PLACEHOLDER: False,
            VProps.PROJECT_ID: project
        }

        sample_timestamp = entity_event[SyncProps.SAMPLE_DATE]

        # TODO(Alexey): need to check here that only the UPDATE sync_mode will
        #               update the UPDATE_TIMESTAMP property
        update_timestamp = self._format_update_timestamp(
            extract_field_value(entity_event, SyncProps.SAMPLE_DATE),
            sample_timestamp)

        return graph_utils.create_vertex(
            self._create_entity_key(entity_event),
            entity_id=entity_id,
            entity_category=EntityCategory.RESOURCE,
            entity_type=NOVA_INSTANCE_PLUGIN,
            entity_state=state,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_neighbors(self, entity_event):

        neighbors = []
        host_transformer = self.transformers[NOVA_HOST_PLUGIN]

        host_name = 'host' if tbase.is_update_event(entity_event) \
            else 'OS-EXT-SRV-ATTR:host'

        if host_transformer:
            host_neighbor = self._create_host_neighbor(
                self._create_entity_key(entity_event),
                extract_field_value(entity_event, host_name),
                entity_event[SyncProps.SAMPLE_DATE],
                host_transformer)
            neighbors.append(host_neighbor)
        else:
            LOG.warning('Cannot find host transformer')

        return neighbors

    def _extract_action_type(self, entity_event):
        sync_mode = entity_event[SyncProps.SYNC_MODE]

        if SyncMode.UPDATE == sync_mode:
            return self.UPDATE_EVENT_TYPES.get(
                entity_event[SyncProps.EVENT_TYPE],
                EventAction.UPDATE_ENTITY)
            return self.EVENT_TYPES.get(entity_event[SyncProps.EVENT_TYPE],
                                        EventAction.UPDATE_ENTITY)

        if SyncMode.SNAPSHOT == sync_mode:
            return EventAction.UPDATE_ENTITY

        if SyncMode.INIT_SNAPSHOT == sync_mode:
            return EventAction.CREATE_ENTITY

        raise VitrageTransformerError('Invalid sync mode: (%s)' % sync_mode)

    def _create_entity_key(self, event):

        instance_id = 'instance_id' if tbase.is_update_event(event) else 'id'
        key_fields = self._key_values(NOVA_INSTANCE_PLUGIN,
                                      extract_field_value(event,
                                                          instance_id))
        return tbase.build_key(key_fields)

    @staticmethod
    def _create_host_neighbor(vertex_id,
                              host_name,
                              sample_timestamp,
                              host_transformer):
        properties = {
            VProps.ID: host_name,
            VProps.SAMPLE_TIMESTAMP: sample_timestamp
        }
        host_vertex = host_transformer.create_placeholder_vertex(**properties)

        relationship_edge = graph_utils.create_edge(
            source_id=host_vertex.vertex_id,
            target_id=vertex_id,
            relationship_type=EdgeLabels.CONTAINS)

        return Neighbor(host_vertex, relationship_edge)

    def create_placeholder_vertex(self, **kwargs):
        if VProps.ID not in kwargs:
            LOG.error('Cannot create placeholder vertex. Missing property ID')
            raise ValueError('Missing property ID')

        key_fields = self._key_values(NOVA_INSTANCE_PLUGIN, kwargs[VProps.ID])

        return graph_utils.create_vertex(
            tbase.build_key(key_fields),
            entity_id=kwargs[VProps.ID],
            entity_category=EntityCategory.RESOURCE,
            entity_type=NOVA_INSTANCE_PLUGIN,
            sample_timestamp=kwargs[VProps.SAMPLE_TIMESTAMP],
            is_placeholder=True)
