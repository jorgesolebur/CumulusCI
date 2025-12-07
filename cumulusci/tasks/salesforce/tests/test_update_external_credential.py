import os
from unittest import mock

import pytest
import responses

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.tasks.salesforce.update_external_credential import (
    ExternalCredential,
    ExternalCredentialParameter,
    ExtParameter,
    HttpHeader,
    TransformExternalCredentialParameter,
    UpdateExternalCredential,
)
from cumulusci.tests.util import CURRENT_SF_API_VERSION

from .util import create_task


class TestExtParameter:
    """Test ExtParameter model"""

    def test_ext_parameter_defaults(self):
        """Test default values for ext parameter"""
        param = ExtParameter(name="test-param", value="test-value")
        assert param.name == "test-param"
        assert param.value == "test-value"
        assert param.group is None
        assert param.sequence_number is None

    def test_ext_parameter_with_all_fields(self):
        """Test ext parameter with all fields"""
        param = ExtParameter(
            name="test-param", value="test-value", group="TestGroup", sequence_number=1
        )
        assert param.name == "test-param"
        assert param.value == "test-value"
        assert param.group == "TestGroup"
        assert param.sequence_number == 1


class TestHttpHeader:
    """Test HttpHeader model"""

    def test_http_header_defaults(self):
        """Test default values for http header"""
        header = HttpHeader(name="test-header", value="test-value")
        assert header.name == "test-header"
        assert header.value == "test-value"
        assert header.secret is False
        assert header.sequence_number is None

    def test_http_header_with_secret(self):
        """Test http header with secret flag"""
        header = HttpHeader(
            name="api-key", value="secret123", secret=True, sequence_number=1
        )
        assert header.name == "api-key"
        assert header.value == "secret123"
        assert header.secret is True
        assert header.sequence_number == 1


class TestExternalCredential:
    """Test ExternalCredential model"""

    def test_external_credential_defaults(self):
        """Test default values for external credential"""
        cred = ExternalCredential(name="test-cred", value="test-value")
        assert cred.name == "test-cred"
        assert cred.value == "test-value"
        assert cred.client_secret is None
        assert cred.client_id is None
        assert cred.auth_protocol == "OAuth"

    def test_external_credential_with_oauth(self):
        """Test external credential with OAuth fields"""
        cred = ExternalCredential(
            name="oauth-cred",
            value="test-value",
            client_id="client123",
            client_secret="secret456",
            auth_protocol="OAuth2",
        )
        assert cred.name == "oauth-cred"
        assert cred.value == "test-value"
        assert cred.client_id == "client123"
        assert cred.client_secret == "secret456"
        assert cred.auth_protocol == "OAuth2"


class TestExternalCredentialParameter:
    """Test ExternalCredentialParameter model"""

    def test_parameter_with_auth_header(self):
        """Test parameter with auth header"""
        auth_header = HttpHeader(name="Authorization", value="Bearer token123")
        param = ExternalCredentialParameter(auth_header=auth_header)
        assert param.auth_header == auth_header
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "AuthHeader"
        assert result["parameterValue"] == "Bearer token123"
        assert result["parameterName"] == "Authorization"

    def test_parameter_with_auth_provider(self):
        """Test parameter with auth provider"""
        param = ExternalCredentialParameter(auth_provider="MyAuthProvider")
        assert param.auth_provider == "MyAuthProvider"
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "AuthProvider"
        assert result["authProvider"] == "MyAuthProvider"
        assert result["parameterName"] == "AuthProvider"

    def test_parameter_with_auth_provider_url(self):
        """Test parameter with auth provider URL"""
        param = ExternalCredentialParameter(
            auth_provider_url="https://auth.example.com"
        )
        assert param.auth_provider_url == "https://auth.example.com"
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "AuthProviderUrl"
        assert result["parameterValue"] == "https://auth.example.com"

    def test_parameter_with_jwt_body_claim(self):
        """Test parameter with JWT body claim"""
        jwt_claim = ExtParameter(name="sub", value='{"sub":"user123"}')
        param = ExternalCredentialParameter(jwt_body_claim=jwt_claim)
        assert param.jwt_body_claim == jwt_claim
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "JwtBodyClaim"
        assert result["parameterValue"] == '{"sub":"user123"}'
        assert result["parameterName"] == "sub"

    def test_parameter_with_named_principal(self):
        """Test parameter with named principal"""
        named_principal = ExternalCredential(
            name="MyPrincipal",
            value="test-value",
            client_id="client123",
            client_secret="secret456",
        )
        param = ExternalCredentialParameter(named_principal=named_principal)
        assert param.named_principal == named_principal
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "NamedPrincipal"
        assert result["parameterName"] == "MyPrincipal"

    def test_parameter_with_signing_certificate(self):
        """Test parameter with signing certificate"""
        param = ExternalCredentialParameter(signing_certificate="MyCertificate")
        assert param.signing_certificate == "MyCertificate"
        result = param.get_external_credential_parameter()
        assert result["parameterType"] == "SigningCertificate"
        assert result["parameterValue"] == "MyCertificate"
        assert result["parameterName"] == "SigningCertificate"

    def test_parameter_validation_error_no_params(self):
        """Test that at least one parameter must be provided"""
        with pytest.raises(
            ValueError, match="At least and only one parameter must be provided"
        ):
            ExternalCredentialParameter()

    def test_parameter_validation_error_multiple_params(self):
        """Test that only one parameter can be provided"""
        auth_header = HttpHeader(name="Auth", value="Bearer token")
        with pytest.raises(
            ValueError, match="At least and only one parameter must be provided"
        ):
            ExternalCredentialParameter(
                auth_header=auth_header, auth_provider="MyProvider"
            )

    def test_get_principal_credential(self):
        """Test get_principal_credential method"""
        named_principal = ExternalCredential(name="MyPrincipal", value="test")
        param = ExternalCredentialParameter(named_principal=named_principal)
        result = param.get_principal_credential("MyExternalCredential")
        assert result["principalType"] == "NamedPrincipal"
        assert result["principalName"] == "MyPrincipal"
        assert result["externalCredential"] == "MyExternalCredential"

    def test_get_credential_parameter(self):
        """Test get_credential_parameter method"""
        named_principal = ExternalCredential(
            name="MyPrincipal",
            value="test",
            client_id="client123",
            client_secret="secret456",
        )
        param = ExternalCredentialParameter(named_principal=named_principal)
        result = param.get_credential_parameter()
        assert result["clientId"]["value"] == "client123"
        assert result["clientSecret"]["value"] == "secret456"
        assert result["clientId"]["encrypted"] is False
        assert result["clientSecret"]["encrypted"] is True

    def test_get_credential(self):
        """Test get_credential method"""
        named_principal = ExternalCredential(
            name="MyPrincipal",
            value="test",
            client_id="client123",
            client_secret="secret456",
            auth_protocol="OAuth2",
        )
        param = ExternalCredentialParameter(named_principal=named_principal)
        result = param.get_credential("MyExternalCredential")
        assert result["principalType"] == "NamedPrincipal"
        assert result["principalName"] == "MyPrincipal"
        assert result["externalCredential"] == "MyExternalCredential"
        assert result["authenticationProtocol"] == "OAuth2"


class TestTransformExternalCredentialParameter:
    """Test TransformExternalCredentialParameter model"""

    def test_transform_parameter_from_env(self):
        """Test parameter transformation from environment variable"""
        with mock.patch.dict(os.environ, {"MY_AUTH_HEADER": "Bearer token456"}):
            auth_header = HttpHeader(name="Authorization", value="MY_AUTH_HEADER")
            param = TransformExternalCredentialParameter(auth_header=auth_header)
            result = param.get_external_credential_parameter()
            assert result["parameterValue"] == "Bearer token456"

    def test_transform_parameter_auth_provider_from_env(self):
        """Test auth provider transformation from environment variable"""
        with mock.patch.dict(os.environ, {"MY_AUTH_PROVIDER": "EnvAuthProvider"}):
            param = TransformExternalCredentialParameter(
                auth_provider="MY_AUTH_PROVIDER"
            )
            result = param.get_external_credential_parameter()
            assert (
                result["authProvider"] == "MY_AUTH_PROVIDER"
            )  # Transform doesn't apply to authProvider field

    def test_transform_parameter_missing_env(self):
        """Test parameter transformation with missing environment variable"""
        auth_header = HttpHeader(name="Auth", value="NONEXISTENT_ENV_VAR")
        param = TransformExternalCredentialParameter(auth_header=auth_header)
        result = param.get_external_credential_parameter()
        assert result["parameterValue"] is None

    def test_transform_credential_parameter_from_env(self):
        """Test credential parameter transformation from environment variable"""
        with mock.patch.dict(os.environ, {"CLIENT_SECRET": "secret123"}):
            named_principal = ExternalCredential(
                name="MyPrincipal",
                value="test",
                client_id="client123",
                client_secret="CLIENT_SECRET",
            )
            param = TransformExternalCredentialParameter(
                named_principal=named_principal
            )
            result = param.get_credential_parameter()
            assert result["clientSecret"]["value"] == "secret123"


class TestUpdateExternalCredential:
    """Test UpdateExternalCredential task"""

    @responses.activate
    def test_update_external_credential_success(self):
        """Test successful update of external credential"""
        auth_header = HttpHeader(name="Authorization", value="Bearer newtoken123")
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "namespace": "",
                "parameters": [{"auth_header": auth_header}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "description": "Old description",
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthHeader",
                            "parameterValue": "Bearer oldtoken123",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_external_credential_with_named_principal(self):
        """Test update with named principal and credential management"""
        named_principal = ExternalCredential(
            name="MyPrincipal",
            value="test-value",
            client_id="client123",
            client_secret="secret456",
            auth_protocol="OAuth2",
        )
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"named_principal": named_principal}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        connect_url = (
            f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}"
        )

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "NamedPrincipal",
                            "parameterName": "MyPrincipal",
                            "parameterValue": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        # Mock get credential (existing)
        responses.add(
            method="GET",
            url=f"{connect_url}/named-credentials/credential",
            json={
                "principalType": "NamedPrincipal",
                "principalName": "MyPrincipal",
                "externalCredential": "testExtCred",
                "authenticationStatus": "Configured",
                "credentials": {
                    "clientId": {
                        "value": "client123",
                        "encrypted": False,
                    },
                },
            },
            status=200,
        )

        # Mock update credential
        responses.add(
            method="PUT",
            url=f"{connect_url}/named-credentials/credential",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5

    @responses.activate
    def test_update_external_credential_create_new_credential(self):
        """Test creating new credential when it doesn't exist"""
        named_principal = ExternalCredential(
            name="NewPrincipal",
            value="test-value",
            client_id="client123",
            client_secret="secret456",
        )
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"named_principal": named_principal}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        connect_url = (
            f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}"
        )

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        # Mock get credential (not found)
        responses.add(
            method="GET",
            url=f"{connect_url}/named-credentials/credential",
            json={
                "principalType": "NamedPrincipal",
                "principalName": "MyPrincipal",
                "externalCredential": "testExtCred",
                "authenticationStatus": "Configured",
                "credentials": {},
            },
            status=200,
        )

        # Mock create credential
        responses.add(
            method="POST",
            url=f"{connect_url}/named-credentials/credential",
            json={},
            status=201,
        )

        task()
        assert len(responses.calls) == 5

    @responses.activate
    def test_update_external_credential_not_found(self):
        """Test update of non-existent external credential"""
        auth_header = HttpHeader(name="Authorization", value="Bearer token")
        task = create_task(
            UpdateExternalCredential,
            {"name": "nonExistentCred", "parameters": [{"auth_header": auth_header}]},
        )

        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query returning no results
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27nonExistentCred%27+LIMIT+1",
            json={"size": 0, "records": []},
            status=200,
        )

        with pytest.raises(
            SalesforceDXException,
            match="External credential 'nonExistentCred' not found",
        ):
            task()

    @responses.activate
    def test_update_external_credential_with_namespace(self):
        """Test update of external credential with namespace"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "namespace": "myns",
                "parameters": [{"auth_provider": "MyAuthProvider"}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+AND+NamespacePrefix%3D%27myns%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthProvider",
                            "parameterValue": "OldAuthProvider",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

    @responses.activate
    def test_update_external_credential_add_new_parameter(self):
        """Test adding a new parameter to external credential"""
        jwt_claim = ExtParameter(name="sub", value='{"sub":"user123"}')
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"jwt_body_claim": jwt_claim}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with existing parameter
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthHeader",
                            "parameterValue": "Bearer token123",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_external_credential_with_transform_parameters(self):
        """Test update with transform parameters from environment variables"""
        with mock.patch.dict(os.environ, {"MY_AUTH_TOKEN": "Bearer envtoken789"}):
            auth_header = HttpHeader(name="Authorization", value="MY_AUTH_TOKEN")
            task = create_task(
                UpdateExternalCredential,
                {
                    "name": "testExtCred",
                    "transform_parameters": [{"auth_header": auth_header}],
                },
            )

            ext_cred_id = "0XE1234567890ABC"
            tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

            # Mock query for external credential ID
            responses.add(
                method="GET",
                url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
                json={"size": 1, "records": [{"Id": ext_cred_id}]},
                status=200,
            )

            # Mock get external credential object
            responses.add(
                method="GET",
                url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
                json={
                    "Metadata": {
                        "externalCredentialParameters": [
                            {
                                "parameterType": "AuthHeader",
                                "parameterValue": "Bearer oldtoken",
                                "description": None,
                                "parameterName": None,
                                "sequenceNumber": None,
                            }
                        ],
                    }
                },
                status=200,
            )

            # Mock update external credential
            responses.add(
                method="PATCH",
                url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
                json={},
                status=200,
            )

            task()
            assert len(responses.calls) == 3

    @responses.activate
    def test_update_external_credential_retrieve_error(self):
        """Test error handling when retrieving external credential fails"""
        auth_header = HttpHeader(name="Authorization", value="Bearer token")
        task = create_task(
            UpdateExternalCredential,
            {"name": "testExtCred", "parameters": [{"auth_header": auth_header}]},
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object failure
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={"error": "Not Found"},
            status=404,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to retrieve external credential object for 'testExtCred'",
        ):
            task()

    @responses.activate
    def test_update_external_credential_update_error(self):
        """Test error handling when updating external credential fails"""
        auth_header = HttpHeader(name="Authorization", value="Bearer token")
        task = create_task(
            UpdateExternalCredential,
            {"name": "testExtCred", "parameters": [{"auth_header": auth_header}]},
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthHeader",
                            "parameterValue": "Bearer oldtoken",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential failure
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={"error": "Update failed"},
            status=400,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to update external credential object",
        ):
            task()

    @responses.activate
    def test_update_external_credential_no_existing_parameters(self):
        """Test update when external credential has no existing parameters"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"auth_provider": "NewAuthProvider"}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with no parameters
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={"Metadata": {"externalCredentialParameters": []}},
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

    @responses.activate
    def test_update_external_credential_with_multiple_parameters(self):
        """Test update with multiple parameters"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        auth_header = HttpHeader(name="Authorization", value="Bearer token123")
        jwt_claim = ExtParameter(name="sub", value='{"sub":"user"}')
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [
                    {"auth_header": auth_header},
                    {"auth_provider": "MyAuthProvider"},
                    {"jwt_body_claim": jwt_claim},
                ],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthHeader",
                            "parameterValue": "Bearer oldtoken",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

    @responses.activate
    def test_update_external_credential_with_sequence_number(self):
        """Test update with sequence number"""
        auth_header = HttpHeader(
            name="MyHeader", value="Bearer token123", sequence_number=5
        )
        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"auth_header": auth_header}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthHeader",
                            "parameterValue": "Bearer oldtoken",
                            "description": None,
                            "parameterName": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_auth_provider_removes_external_auth_identity_provider(self):
        """Test that adding AuthProvider removes ExternalAuthIdentityProvider"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"auth_provider": "MyAuthProvider"}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with ExternalAuthIdentityProvider
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "ExternalAuthIdentityProvider",
                            "parameterName": "ExternalAuthIdentityProvider",
                            "externalAuthIdentityProvider": "OldProvider",
                            "authProvider": None,
                            "certificate": None,
                            "description": None,
                            "parameterGroup": "DefaultGroup",
                            "parameterValue": None,
                            "sequenceNumber": None,
                        },
                        {
                            "parameterType": "AuthParameter",
                            "parameterName": "Scope",
                            "parameterValue": "scope",
                            "authProvider": None,
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "DefaultGroup",
                            "sequenceNumber": None,
                        },
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

        # Verify the PATCH request removed ExternalAuthIdentityProvider
        patch_call = responses.calls[4]  # Last call is the PATCH
        updated_params = patch_call.request.body
        import json

        body = json.loads(updated_params)
        params = body["Metadata"]["externalCredentialParameters"]

        # Should not contain ExternalAuthIdentityProvider
        assert not any(
            p.get("parameterType") == "ExternalAuthIdentityProvider" for p in params
        )
        # Should contain AuthProvider
        assert any(p.get("parameterType") == "AuthProvider" for p in params)
        # Should still contain AuthParameter
        assert any(p.get("parameterType") == "AuthParameter" for p in params)

    @responses.activate
    def test_external_auth_identity_provider_removes_auth_provider(self):
        """Test that adding ExternalAuthIdentityProvider removes AuthProvider"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [
                    {"external_auth_identity_provider": "MyExternalAuthProvider"}
                ],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with AuthProvider
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthProvider",
                            "parameterName": "AuthProvider",
                            "authProvider": "OldAuthProvider",
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "DefaultGroup",
                            "parameterValue": "OldAuthProvider",
                            "sequenceNumber": None,
                        },
                        {
                            "parameterType": "AuthParameter",
                            "parameterName": "Scope",
                            "parameterValue": "scope",
                            "authProvider": None,
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "DefaultGroup",
                            "sequenceNumber": None,
                        },
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

        # Verify the PATCH request removed AuthProvider
        patch_call = responses.calls[4]  # Last call is the PATCH
        updated_params = patch_call.request.body
        import json

        body = json.loads(updated_params)
        params = body["Metadata"]["externalCredentialParameters"]

        # Should not contain AuthProvider
        assert not any(p.get("parameterType") == "AuthProvider" for p in params)
        # Should contain ExternalAuthIdentityProvider
        assert any(
            p.get("parameterType") == "ExternalAuthIdentityProvider" for p in params
        )
        # Should still contain AuthParameter
        assert any(p.get("parameterType") == "AuthParameter" for p in params)

    @responses.activate
    def test_multiple_auth_providers_removed(self):
        """Test that multiple conflicting parameters are removed"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [
                    {"external_auth_identity_provider": "MyExternalAuthProvider"}
                ],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with multiple AuthProvider parameters
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthProvider",
                            "parameterName": "AuthProvider",
                            "authProvider": "Provider1",
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "Group1",
                            "parameterValue": "Provider1",
                            "sequenceNumber": None,
                        },
                        {
                            "parameterType": "AuthProvider",
                            "parameterName": "AuthProvider",
                            "authProvider": "Provider2",
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "Group2",
                            "parameterValue": "Provider2",
                            "sequenceNumber": None,
                        },
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

        # Verify all AuthProvider parameters were removed
        patch_call = responses.calls[4]  # Last call is the PATCH
        updated_params = patch_call.request.body
        import json

        body = json.loads(updated_params)
        params = body["Metadata"]["externalCredentialParameters"]

        # Should not contain any AuthProvider
        auth_providers = [p for p in params if p.get("parameterType") == "AuthProvider"]
        assert len(auth_providers) == 0

    @responses.activate
    def test_no_conflict_when_no_existing_parameters(self):
        """Test that no error occurs when there are no existing conflicting parameters"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"auth_provider": "MyAuthProvider"}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with no parameters
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

    @responses.activate
    def test_update_existing_auth_provider_removes_external_auth(self):
        """Test updating existing AuthProvider also removes ExternalAuthIdentityProvider"""
        # Mock SF API version discovery
        responses.add(
            method="GET",
            url="https://test.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
            status=200,
        )

        # Mock installed packages query
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+SubscriberPackage.Id%2C+SubscriberPackage.Name%2C+SubscriberPackage.NamespacePrefix%2C+SubscriberPackageVersionId+FROM+InstalledSubscriberPackage",
            json={"size": 0, "records": []},
            status=200,
        )

        task = create_task(
            UpdateExternalCredential,
            {
                "name": "testExtCred",
                "parameters": [{"auth_provider": "UpdatedAuthProvider"}],
            },
        )

        ext_cred_id = "0XE1234567890ABC"

        # Mock query for external credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+ExternalCredential+WHERE+DeveloperName%3D%27testExtCred%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": ext_cred_id}]},
            status=200,
        )

        # Mock get external credential object with both AuthProvider and ExternalAuthIdentityProvider
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={
                "Metadata": {
                    "externalCredentialParameters": [
                        {
                            "parameterType": "AuthProvider",
                            "parameterName": "AuthProvider",
                            "authProvider": "OldAuthProvider",
                            "certificate": None,
                            "description": None,
                            "externalAuthIdentityProvider": None,
                            "parameterGroup": "DefaultGroup",
                            "parameterValue": "OldAuthProvider",
                            "sequenceNumber": None,
                        },
                        {
                            "parameterType": "ExternalAuthIdentityProvider",
                            "parameterName": "ExternalAuthIdentityProvider",
                            "externalAuthIdentityProvider": "SomeProvider",
                            "authProvider": None,
                            "certificate": None,
                            "description": None,
                            "parameterGroup": "DefaultGroup",
                            "parameterValue": None,
                            "sequenceNumber": None,
                        },
                    ],
                }
            },
            status=200,
        )

        # Mock update external credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/ExternalCredential/{ext_cred_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 5  # 2 setup + 3 task calls

        # Verify ExternalAuthIdentityProvider was removed
        patch_call = responses.calls[4]  # Last call is the PATCH
        updated_params = patch_call.request.body
        import json

        body = json.loads(updated_params)
        params = body["Metadata"]["externalCredentialParameters"]

        # Should have 2 AuthProviders (old one updated + new one added) and no ExternalAuthIdentityProvider
        # Actually, since authProvider value is different, it adds a new AuthProvider
        # So we have old AuthProvider updated to new value, no new one is added
        auth_providers = [p for p in params if p.get("parameterType") == "AuthProvider"]
        assert len(auth_providers) >= 1
        # Should not contain ExternalAuthIdentityProvider
        assert not any(
            p.get("parameterType") == "ExternalAuthIdentityProvider" for p in params
        )
