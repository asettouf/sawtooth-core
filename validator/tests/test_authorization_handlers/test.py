# Copyright 2017 Intel Corporation
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
# ------------------------------------------------------------------------------
import unittest
import os

import sawtooth_signing as signing

from sawtooth_validator.networking.interconnect import AuthorizationType
from sawtooth_validator.networking.interconnect import ConnectionStatus
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.networking.handlers import ConnectHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationTrustRequestHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationChallengeRequestHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationChallengeSubmitHandler

from sawtooth_validator.protobuf.authorization_pb2 import ConnectionRequest
from sawtooth_validator.protobuf.authorization_pb2 import RoleType
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationTrustRequest
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeRequest
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeSubmit
from sawtooth_validator.protobuf import validator_pb2

from test_authorization_handlers.mock import MockNetwork
from test_authorization_handlers.mock import MockPermissionVerifier
from test_authorization_handlers.mock import MockGossip


class TestAuthorizationHandlers(unittest.TestCase):

    def test_connect(self):
        """
        Test the ConnectHandler correctly responds to a ConnectionRequest.
        """
        connect_message = ConnectionRequest(endpoint="endpoint")
        roles = {"network": AuthorizationType.TRUST}
        network = MockNetwork(roles)
        handler = ConnectHandler(network)
        handler_status = handler.handle("connection_id",
                                        connect_message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE)

    def test_connect_bad_endpoint(self):
        """
        Test the ConnectHandler correctly responds to a ConnectionRequest.
        """
        connect_message = ConnectionRequest(endpoint="tcp://0.0.0.0:8800")
        roles = {"network": AuthorizationType.TRUST}
        network = MockNetwork(roles)
        handler = ConnectHandler(network)
        handler_status = handler.handle("connection_id",
                                        connect_message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE)

    def test_connect_bad_role_type(self):
        """
        Test the ConnectHandler closes the connection if the role has an
        unsupported role type.
        """
        connect_message = ConnectionRequest(endpoint="endpoint")
        roles = {"network": "other"}
        network = MockNetwork(roles)
        handler = ConnectHandler(network)
        handler_status = handler.handle("connection_id",
                                        connect_message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE)

    def test_connect_not_allowing_incoming_connections(self):
        """
        Test the ConnectHandler closes a connection if we are not accepting
        incoming connections
        """
        connect_message = ConnectionRequest(endpoint="endpoint")
        roles = {"network": AuthorizationType.TRUST}
        network = MockNetwork(roles, allow_inbound=False)
        handler = ConnectHandler(network)
        handler_status = handler.handle("connection_id",
                                        connect_message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE)

    def test_connect_wrong_previous_message(self):
        """
        Test the ConnectHandler closes a connection if any authorization
        message has been recieved before this connection request.
        """
        connect_message = ConnectionRequest(endpoint="endpoint")
        roles = {"network": AuthorizationType.TRUST}
        network = MockNetwork(roles,
                              connection_status={"connection_id":"other"})
        handler = ConnectHandler(network)
        handler_status = handler.handle("connection_id",
                                        connect_message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE)

    def test_authorization_trust_request(self):
        """
        Test the AuthorizationTrustRequestHandler returns an
        AuthorizationTrustResponse if the AuthorizationTrustRequest should be
        approved.
        """
        auth_trust_request = AuthorizationTrustRequest(
            roles=[RoleType.Value("NETWORK")],
            public_key="public_key")

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.CONNECTION_REQUEST})
        permission_verifer = MockPermissionVerifier()
        gossip = MockGossip()
        handler = AuthorizationTrustRequestHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_trust_request.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_TRUST_RESPONSE)

    def test_authorization_trust_request_bad_last_message(self):
        """
        Test the AuthorizationTrustRequestHandler returns an
        AuthorizationViolation and closes the connection if the last message
        was not a ConnectionRequest.
        """
        auth_trust_request = AuthorizationTrustRequest(
            roles=[RoleType.Value("NETWORK")],
            public_key="public_key")

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               "other"})
        permission_verifer = MockPermissionVerifier()
        gossip = MockGossip()
        handler = AuthorizationTrustRequestHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_trust_request.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def test_authorization_trust_request_not_permitted(self):
        """
        Test the AuthorizationTrustRequestHandler returns an
        AuthorizationViolation and closes the connection if the permission
        verifier does not permit the connections public key.
        """
        auth_trust_request = AuthorizationTrustRequest(
            roles=[RoleType.Value("NETWORK")],
            public_key="public_key")

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.CONNECTION_REQUEST})
        # say that connection is not permitted
        permission_verifer = MockPermissionVerifier(allow=False)
        gossip = MockGossip()

        handler = AuthorizationTrustRequestHandler(
            network, permission_verifer, gossip)

        handler_status = handler.handle(
            "connection_id",
            auth_trust_request.SerializeToString())

        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def test_authorization_challenge_request(self):
        """
        Test the AuthorizationChallengeRequestHandler returns an
        AuthorizationChallengeResponse.
        """
        auth_challenge_request = AuthorizationChallengeRequest()
        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.CONNECTION_REQUEST})
        handler = AuthorizationChallengeRequestHandler(network)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_request.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESPONSE)

    def test_authorization_challenge_request_bad_last_message(self):
        """
        Test the AuthorizationChallengeRequestHandler returns an
        AuthorizationViolation and closes the connection if the last message
        was not a ConnectionRequst
        """
        auth_challenge_request = AuthorizationChallengeRequest()
        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               "other"})
        handler = AuthorizationChallengeRequestHandler(network)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_request.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def test_authorization_challenge_submit(self):
        """
        Test the AuthorizationChallengeSubmitHandler returns an
        AuthorizationChallengeResult.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)
        payload = os.urandom(10)

        signature = signing.sign(payload, private_key)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key=public_key,
            payload=payload,
            signature=signature,
            roles=[RoleType.Value("NETWORK")])

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.AUTH_CHALLENGE_REQUEST})
        permission_verifer = MockPermissionVerifier()
        gossip = MockGossip()
        handler = AuthorizationChallengeSubmitHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_submit.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESULT)

    def test_authorization_challenge_submit_bad_last_message(self):
        """
        Test the AuthorizationChallengeSubmitHandler returns an
        AuthorizationViolation and closes the connection if the last message
        was not AuthorizaitonChallengeRequest.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)
        payload = os.urandom(10)

        signature = signing.sign(payload, private_key)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key=public_key,
            payload=payload,
            signature=signature,
            roles=[RoleType.Value("NETWORK")])

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               "other"})
        permission_verifer = MockPermissionVerifier()
        gossip = MockGossip()
        handler = AuthorizationChallengeSubmitHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_submit.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def test_authorization_challenge_submit_bad_signature(self):
        """
        Test the AuthorizationChallengeSubmitHandler returns an
        AuthorizationViolation and closes the connection if the signature
        is not verified.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)
        payload = os.urandom(10)

        signature = signing.sign(payload, private_key)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key="other",
            payload=payload,
            signature=signature,
            roles=[RoleType.Value("NETWORK")])

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.AUTH_CHALLENGE_REQUEST})
        permission_verifer = MockPermissionVerifier()
        gossip = MockGossip()
        handler = AuthorizationChallengeSubmitHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_submit.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def test_authorization_challenge_submit(self):
        """
        Test the AuthorizationChallengeSubmitHandler returns an
        AuthorizationViolation and closes the connection if the permission
        verifier does not permit the public_key.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)
        payload = os.urandom(10)

        signature = signing.sign(payload, private_key)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key=public_key,
            payload=payload,
            signature=signature,
            roles=[RoleType.Value("NETWORK")])

        roles = {"network": AuthorizationType.TRUST}

        network = MockNetwork(
            roles,
            connection_status={"connection_id":
                               ConnectionStatus.AUTH_CHALLENGE_REQUEST})
        permission_verifer = MockPermissionVerifier(allow=False)
        gossip = MockGossip()
        handler = AuthorizationChallengeSubmitHandler(
            network, permission_verifer, gossip)
        handler_status = handler.handle(
            "connection_id",
            auth_challenge_submit.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.RETURN_AND_CLOSE)
        self.assertEqual(
            handler_status.message_type,
            validator_pb2.Message.AUTHORIZATION_VIOLATION)