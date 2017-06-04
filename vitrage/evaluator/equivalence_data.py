# Copyright 2017 - ZTE Corporation
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

from vitrage.common.constants import TemplateTopologyFields


class Fields(TemplateTopologyFields):

    EQUIVALENCES = 'equivalences'
    EQUIVALENCE = 'equivalence'


# noinspection PyAttributeOutsideInit
class EquivalenceData(object):

    def __init__(self, equivalence_def):

        self.name = equivalence_def[Fields.METADATA][Fields.NAME]

        self._equivalences = self._build_equivalences(
            equivalence_def[Fields.EQUIVALENCES])

    @property
    def equivalences(self):
        return self._equivalences

    @staticmethod
    def _build_equivalences(equivalence_defs):
        """equivalence stored as arrays of frozen entity sets

        equivalences:: [equivalence, ...]
        equivalence:: {entity, ...}
        entity:: {(k,v), ...}
        """
        equivalences = []
        for equivalence_def in equivalence_defs:
            equivalent_entities = equivalence_def[Fields.EQUIVALENCE]
            equivalence = []
            for entity_def in equivalent_entities:
                equivalence.append(frozenset(entity_def[Fields.ENTITY]
                                             .items()))
            equivalences.append(frozenset(equivalence))
        return equivalences