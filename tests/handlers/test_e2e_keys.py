# -*- coding: utf-8 -*-
# Copyright 2016 OpenMarket Ltd
# Copyright 2019 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from twisted.internet import defer

import synapse.api.errors
import synapse.handlers.e2e_keys
import synapse.storage
from synapse.api import errors

from tests import unittest, utils


class E2eKeysHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(E2eKeysHandlerTestCase, self).__init__(*args, **kwargs)
        self.hs = None  # type: synapse.server.HomeServer
        self.handler = None  # type: synapse.handlers.e2e_keys.E2eKeysHandler

    @defer.inlineCallbacks
    def setUp(self):
        self.hs = yield utils.setup_test_homeserver(
            self.addCleanup, handlers=None, federation_client=mock.Mock()
        )
        self.handler = synapse.handlers.e2e_keys.E2eKeysHandler(self.hs)

    @defer.inlineCallbacks
    def test_query_local_devices_no_devices(self):
        """If the user has no devices, we expect an empty list.
        """
        local_user = "@boris:" + self.hs.hostname
        res = yield self.handler.query_local_devices({local_user: None})
        self.assertDictEqual(res, {local_user: {}})

    @defer.inlineCallbacks
    def test_reupload_one_time_keys(self):
        """we should be able to re-upload the same keys"""
        local_user = "@boris:" + self.hs.hostname
        device_id = "xyz"
        keys = {
            "alg1:k1": "key1",
            "alg2:k2": {"key": "key2", "signatures": {"k1": "sig1"}},
            "alg2:k3": {"key": "key3"},
        }

        res = yield self.handler.upload_keys_for_user(
            local_user, device_id, {"one_time_keys": keys}
        )
        self.assertDictEqual(res, {"one_time_key_counts": {"alg1": 1, "alg2": 2}})

        # we should be able to change the signature without a problem
        keys["alg2:k2"]["signatures"]["k1"] = "sig2"
        res = yield self.handler.upload_keys_for_user(
            local_user, device_id, {"one_time_keys": keys}
        )
        self.assertDictEqual(res, {"one_time_key_counts": {"alg1": 1, "alg2": 2}})

    @defer.inlineCallbacks
    def test_change_one_time_keys(self):
        """attempts to change one-time-keys should be rejected"""

        local_user = "@boris:" + self.hs.hostname
        device_id = "xyz"
        keys = {
            "alg1:k1": "key1",
            "alg2:k2": {"key": "key2", "signatures": {"k1": "sig1"}},
            "alg2:k3": {"key": "key3"},
        }

        res = yield self.handler.upload_keys_for_user(
            local_user, device_id, {"one_time_keys": keys}
        )
        self.assertDictEqual(res, {"one_time_key_counts": {"alg1": 1, "alg2": 2}})

        try:
            yield self.handler.upload_keys_for_user(
                local_user, device_id, {"one_time_keys": {"alg1:k1": "key2"}}
            )
            self.fail("No error when changing string key")
        except errors.SynapseError:
            pass

        try:
            yield self.handler.upload_keys_for_user(
                local_user, device_id, {"one_time_keys": {"alg2:k3": "key2"}}
            )
            self.fail("No error when replacing dict key with string")
        except errors.SynapseError:
            pass

        try:
            yield self.handler.upload_keys_for_user(
                local_user, device_id, {"one_time_keys": {"alg1:k1": {"key": "key"}}}
            )
            self.fail("No error when replacing string key with dict")
        except errors.SynapseError:
            pass

        try:
            yield self.handler.upload_keys_for_user(
                local_user,
                device_id,
                {
                    "one_time_keys": {
                        "alg2:k2": {"key": "key3", "signatures": {"k1": "sig1"}}
                    }
                },
            )
            self.fail("No error when replacing dict key")
        except errors.SynapseError:
            pass

    @defer.inlineCallbacks
    def test_claim_one_time_key(self):
        local_user = "@boris:" + self.hs.hostname
        device_id = "xyz"
        keys = {"alg1:k1": "key1"}

        res = yield self.handler.upload_keys_for_user(
            local_user, device_id, {"one_time_keys": keys}
        )
        self.assertDictEqual(res, {"one_time_key_counts": {"alg1": 1}})

        res2 = yield self.handler.claim_one_time_keys(
            {"one_time_keys": {local_user: {device_id: "alg1"}}}, timeout=None
        )
        self.assertEqual(
            res2,
            {
                "failures": {},
                "one_time_keys": {local_user: {device_id: {"alg1:k1": "key1"}}},
            },
        )

    @defer.inlineCallbacks
    def test_replace_self_signing_key(self):
        """uploading a new signing key should make the old signing key unavailable"""
        local_user = "@boris:" + self.hs.hostname
        keys1 = {
            "self_signing_key": {
                # private key: 2lonYOM6xYKdEsO+6KrC766xBcHnYnim1x/4LFGF8B0
                "user_id": local_user,
                "usage": ["self_signing"],
                "keys": {
                    "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk": "nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk"
                }
            }
        }
        yield self.handler.upload_signing_keys_for_user(local_user, keys1)

        keys2 = {
            "self_signing_key": {
                # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                "user_id": local_user,
                "usage": ["self_signing"],
                "keys": {
                    "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw": "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                },
                "replaces": "nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk"
            }
        }
        yield self.handler.upload_signing_keys_for_user(local_user, keys2)

        devices = yield self.handler.query_devices(
            {"device_keys": {local_user: []}}, 0
        )
        self.assertDictEqual(
            devices,
            {
                "failures": {},
                "device_keys": {local_user: {}},
                "self_signing_keys": {
                    local_user: keys2["self_signing_key"]
                }
            },
        )

    @defer.inlineCallbacks
    def test_bad_replace_self_signing_key(self):
        """replacing a signing key needs to follow rules"""
        local_user = "@boris:" + self.hs.hostname
        keys1 = {
            "self_signing_key": {
                # private key: 2lonYOM6xYKdEsO+6KrC766xBcHnYnim1x/4LFGF8B0
                "user_id": local_user,
                "usage": ["self_signing"],
                "keys": {
                    "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk": "nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk"
                }
            }
        }
        yield self.handler.upload_signing_keys_for_user(local_user, keys1)

        res = None
        try:
            # does not have a "replaces" property
            keys2 = {
                "self_signing_key": {
                    # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                    "user_id": local_user,
                    "usage": ["self_signing"],
                    "keys": {
                        "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw": "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                    },
                }
            }
            yield self.handler.upload_signing_keys_for_user(local_user, keys2)
        except errors.SynapseError as e:
            res = e.code
        self.assertEqual(res, 400)

        res = None
        try:
            # has the wrong ID in replaces
            keys2 = {
                "self_signing_key": {
                    # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                    "user_id": local_user,
                    "usage": ["self_signing"],
                    "keys": {
                        "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw": "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                    },
                    "replaces": "wrong+id"
                }
            }
            yield self.handler.upload_signing_keys_for_user(local_user, keys2)
        except errors.SynapseError as e:
            res = e.code
        self.assertEqual(res, 400)

        res = None
        try:
            # invalid signature from old key
            keys2 = {
                "self_signing_key": {
                    # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                    "user_id": local_user,
                    "usage": ["self_signing"],
                    "keys": {
                        "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw":
                        "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                    },
                    "replaces": "nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk",
                    "signatures": {
                        local_user: {
                            "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk":
                            "this+is+a+bad+signature"
                        }
                    }
                }
            }
            yield self.handler.upload_signing_keys_for_user(local_user, keys2)
        except errors.SynapseError as e:
            res = e.code
        self.assertEqual(res, 400)

    @defer.inlineCallbacks
    def test_bad_replace_user_signing_key(self):
        """setting a user signing key needs to follow rules"""
        local_user = "@boris:" + self.hs.hostname
        keys1 = {
            "self_signing_key": {
                # private key: 2lonYOM6xYKdEsO+6KrC766xBcHnYnim1x/4LFGF8B0
                "user_id": local_user,
                "usage": ["self_signing"],
                "keys": {
                    "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk":
                    "nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk"
                }
            }
        }
        yield self.handler.upload_signing_keys_for_user(local_user, keys1)

        res = None
        try:
            # signature from user key
            keys2 = {
                "user_signing_key": {
                    # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                    "user_id": local_user,
                    "usage": ["user_signing"],
                    "keys": {
                        "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw":
                        "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                    },
                    "signatures": {
                        local_user: {
                            "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk":
                            "this+is+a+bad+signature"
                        }
                    }
                }
            }
            yield self.handler.upload_signing_keys_for_user(local_user, keys2)
        except errors.SynapseError as e:
            res = e.code
        self.assertEqual(res, 400)

        res = None
        try:
            # invalid signature from user key
            keys2 = {
                "user_signing_key": {
                    # private key: 4TL4AjRYwDVwD3pqQzcor+ez/euOB1/q78aTJ+czDNs
                    "user_id": local_user,
                    "usage": ["user_signing"],
                    "keys": {
                        "ed25519:Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw":
                        "Hq6gL+utB4ET+UvD5ci0kgAwsX6qP/zvf8v6OInU5iw"
                    },
                    "signatures": {
                        local_user: {
                            "ed25519:nqOvzeuGWT/sRx3h7+MHoInYj3Uk2LD/unI9kDYcHwk":
                            "this+is+a+bad+signature"
                        }
                    }
                }
            }
            yield self.handler.upload_signing_keys_for_user(local_user, keys2)
        except errors.SynapseError as e:
            res = e.code
        self.assertEqual(res, 400)
