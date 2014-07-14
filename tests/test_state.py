# -*- coding: utf-8 -*-
from twisted.internet import defer
from twisted.trial import unittest

from synapse.state import StateHandler
from synapse.federation.units import Pdu

from collections import namedtuple


ReturnType = namedtuple(
    "StateReturnType", ["new_branch", "current_branch"]
)


class StateTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_replication_layer = MockReplication()
        self.mock_persistence = MockPersistence()

        self.state = StateHandler(
            persistence_service=self.mock_persistence,
            replication_layer=self.mock_replication_layer,
        )

    def test_new_state_key(self):
        new_pdu = new_fake_pdu("A", "test", "mem", "x", None, 10)

        self.mock_persistence.mock_state_tree(
            new_pdu, ReturnType([new_pdu], []))

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((new_pdu.pdu_id, new_pdu.origin), curr_state)

    def test_direct_overwrite(self):
        old_pdu = new_fake_pdu("A", "test", "mem", "x", None, 10)
        new_pdu = new_fake_pdu("B", "test", "mem", "x", "A", 5)

        self.mock_persistence.mock_state_tree(
            new_pdu, ReturnType([new_pdu, old_pdu], [old_pdu]))

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((new_pdu.pdu_id, new_pdu.origin), curr_state)

    def test_power_level_fail(self):
        old_pdu_1 = new_fake_pdu("A", "test", "mem", "x", None, 10)
        old_pdu_2 = new_fake_pdu("B", "test", "mem", "x", None, 10)
        new_pdu = new_fake_pdu("C", "test", "mem", "x", "A", 5)

        self.mock_persistence.mock_state_tree(
            new_pdu, ReturnType([new_pdu, old_pdu_1], [old_pdu_2, old_pdu_1]))

        self.mock_persistence.update_current_state(
            old_pdu_2.pdu_id, old_pdu_2.origin,
            old_pdu_2.context, old_pdu_2.pdu_type, old_pdu_2.state_key
        )

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((old_pdu_2.pdu_id, old_pdu_2.origin), curr_state)

    def test_power_level_succeed(self):
        old_pdu_1 = new_fake_pdu("A", "test", "mem", "x", None, 10)
        old_pdu_2 = new_fake_pdu("B", "test", "mem", "x", None, 10)
        new_pdu = new_fake_pdu("C", "test", "mem", "x", "A", 15)

        self.mock_persistence.mock_state_tree(
            new_pdu, ReturnType([new_pdu, old_pdu_1], [old_pdu_2, old_pdu_1]))

        self.mock_persistence.update_current_state(
            old_pdu_2.pdu_id, old_pdu_2.origin,
            old_pdu_2.context, old_pdu_2.pdu_type, old_pdu_2.state_key
        )

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((new_pdu.pdu_id, new_pdu.origin), curr_state)

    def test_power_level_equal_same_len(self):
        old_pdu_1 = new_fake_pdu("A", "test", "mem", "x", None, 10)
        old_pdu_2 = new_fake_pdu("B", "test", "mem", "x", None, 10)
        new_pdu = new_fake_pdu("C", "test", "mem", "x", "A", 10)

        self.mock_persistence.mock_state_tree(
            new_pdu, ReturnType([new_pdu, old_pdu_1], [old_pdu_2, old_pdu_1]))

        self.mock_persistence.update_current_state(
            old_pdu_2.pdu_id, old_pdu_2.origin,
            old_pdu_2.context, old_pdu_2.pdu_type, old_pdu_2.state_key
        )

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((old_pdu_2.pdu_id, old_pdu_2.origin), curr_state)

    def test_power_level_equal_diff_len(self):
        old_pdu_1 = new_fake_pdu("A", "test", "mem", "x", None, 10)
        old_pdu_2 = new_fake_pdu("B", "test", "mem", "x", None, 10)
        old_pdu_3 = new_fake_pdu("C", "test", "mem", "x", "A", 10)
        new_pdu = new_fake_pdu("D", "test", "mem", "x", "C", 10)

        self.mock_persistence.mock_state_tree(
            new_pdu,
            ReturnType([new_pdu, old_pdu_3, old_pdu_1], [old_pdu_2, old_pdu_1])
        )

        self.mock_persistence.update_current_state(
            old_pdu_2.pdu_id, old_pdu_2.origin,
            old_pdu_2.context, old_pdu_2.pdu_type, old_pdu_2.state_key
        )

        self.state.handle_new_state(new_pdu)

        curr_state = self.mock_persistence.get_current_state(
            new_pdu.context,
            new_pdu.pdu_type,
            new_pdu.state_key
        )

        self.assertEquals((new_pdu.pdu_id, new_pdu.origin), curr_state)


def new_fake_pdu(pdu_id, context, pdu_type, state_key, prev_state_id,
                 power_level):
    new_pdu = Pdu.create_new(
        pdu_id=pdu_id,
        origin="example.com",
        context="context",
        ts=1405353060021,
        pdu_type=pdu_type,
        destinations=[],
        prev_pdus=[],
        depth=0,
        content={},
        state_key=state_key,
        is_state=True,
        power_level=power_level,
        prev_state_id=prev_state_id,
        prev_state_origin="example.com",
    )

    return new_pdu


class MockReplication(object):

    def __init__(self):
        self.pdus = {}

    def mock_get_pdu(self, pdu, destination, pdu_origin, pdu_id, outlier):
        self.pdus[(destination, pdu_origin, pdu_id, outlier)] = pdu

    def get_pdu(self, destination, pdu_origin, pdu_id, outlier=False):
        pdu = self.pdus[(destination, pdu_origin, pdu_id, outlier)]
        return defer.succed(pdu)


class MockPersistence(object):

    def __init__(self):
        self.current_state = {}
        self.state_tree = {}

    def mock_state_tree(self, new_pdu, state_tree):
        self.state_tree[new_pdu] = state_tree

    def get_unresolved_state_tree(self, new_pdu):
        tree = self.state_tree[new_pdu]
        return defer.succeed(tree)

    def update_current_state(self, pdu_id, origin, context, pdu_type,
                             state_key):
        self.current_state[(context, pdu_type, state_key)] = (pdu_id, origin)
        return defer.succeed(None)

    def get_current_state(self, context, pdu_type, state_key):
        pdu = self.current_state[(context, pdu_type, state_key)]
        return pdu