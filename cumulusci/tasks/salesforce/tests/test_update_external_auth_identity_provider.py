import os

import pytest
import responses

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.tasks.salesforce.update_external_auth_identity_provider import (
    ExternalAuthIdentityProviderCredential,
    ExternalAuthIdentityProviderParameter,
    ExtParameter,
    TransformExternalAuthIdentityProviderParameter,
    UpdateExternalAuthIdentityProvider,
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
        assert param.sequence_number is None

    def test_ext_parameter_with_sequence_number(self):
        """Test ext parameter with sequence number"""
        param = ExtParameter(name="test-param", value="test-value", sequence_number=1)
        assert param.name == "test-param"
        assert param.value == "test-value"
        assert param.sequence_number == 1


class TestExternalAuthIdentityProviderCredential:
    """Test ExternalAuthIdentityProviderCredential model"""

    def test_credential_defaults(self):
        """Test default values for credential"""
        cred = ExternalAuthIdentityProviderCredential(
            name="test-cred", client_id="client123", client_secret="secret456"
        )
        assert cred.name == "test-cred"
        assert cred.client_id == "client123"
        assert cred.client_secret == "secret456"
        assert cred.auth_protocol == "OAuth"

    def test_credential_with_custom_protocol(self):
        """Test credential with custom auth protocol"""
        cred = ExternalAuthIdentityProviderCredential(
            name="test-cred",
            client_id="client123",
            client_secret="secret456",
            auth_protocol="OpenIdConnect",
        )
        assert cred.auth_protocol == "OpenIdConnect"


class TestExternalAuthIdentityProviderParameter:
    """Test ExternalAuthIdentityProviderParameter model"""

    def test_parameter_with_authorize_url(self):
        """Test parameter with authorize URL"""
        param = ExternalAuthIdentityProviderParameter(
            authorize_url="https://auth.example.com/authorize"
        )
        assert param.authorize_url == "https://auth.example.com/authorize"

    def test_parameter_with_token_url(self):
        """Test parameter with token URL"""
        param = ExternalAuthIdentityProviderParameter(
            token_url="https://auth.example.com/token"
        )
        assert param.token_url == "https://auth.example.com/token"

    def test_parameter_with_user_info_url(self):
        """Test parameter with user info URL"""
        param = ExternalAuthIdentityProviderParameter(
            user_info_url="https://auth.example.com/userinfo"
        )
        assert param.user_info_url == "https://auth.example.com/userinfo"

    def test_parameter_with_jwks_url(self):
        """Test parameter with JWKS URL"""
        param = ExternalAuthIdentityProviderParameter(
            jwks_url="https://auth.example.com/.well-known/jwks.json"
        )
        assert param.jwks_url == "https://auth.example.com/.well-known/jwks.json"

    def test_parameter_with_issuer_url(self):
        """Test parameter with issuer URL"""
        param = ExternalAuthIdentityProviderParameter(
            issuer_url="https://auth.example.com"
        )
        assert param.issuer_url == "https://auth.example.com"

    def test_parameter_with_client_authentication(self):
        """Test parameter with client authentication"""
        param = ExternalAuthIdentityProviderParameter(
            client_authentication="ClientSecretBasic"
        )
        assert param.client_authentication == "ClientSecretBasic"

    def test_parameter_with_custom_parameter(self):
        """Test parameter with custom parameter"""
        custom_param = ExtParameter(name="scope", value="openid profile email")
        param = ExternalAuthIdentityProviderParameter(custom_parameter=custom_param)
        assert param.custom_parameter == custom_param

    def test_parameter_with_identity_provider_option(self):
        """Test parameter with identity provider option"""
        option = ExtParameter(name="PkceEnabled", value="true")
        param = ExternalAuthIdentityProviderParameter(identity_provider_option=option)
        assert param.identity_provider_option == option

    def test_parameter_with_credential(self):
        """Test parameter with credential"""
        cred = ExternalAuthIdentityProviderCredential(
            name="test-cred", client_id="client123", client_secret="secret456"
        )
        param = ExternalAuthIdentityProviderParameter(credential=cred)
        assert param.credential == cred

    def test_parameter_validation_no_parameters(self):
        """Test validation when no parameters are provided"""
        with pytest.raises(ValueError, match="At least and only one parameter"):
            ExternalAuthIdentityProviderParameter()

    def test_parameter_validation_multiple_parameters(self):
        """Test validation when multiple parameters are provided"""
        with pytest.raises(ValueError, match="At least and only one parameter"):
            ExternalAuthIdentityProviderParameter(
                authorize_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
            )

    def test_get_parameter_authorize_url(self):
        """Test getting parameter for authorize URL"""
        param = ExternalAuthIdentityProviderParameter(
            authorize_url="https://auth.example.com/authorize"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "AuthorizeUrl"
        assert result["parameterName"] == "AuthorizeUrl"
        assert result["parameterValue"] == "https://auth.example.com/authorize"

    def test_get_parameter_token_url(self):
        """Test getting parameter for token URL"""
        param = ExternalAuthIdentityProviderParameter(
            token_url="https://auth.example.com/token"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "TokenUrl"
        assert result["parameterName"] == "TokenUrl"
        assert result["parameterValue"] == "https://auth.example.com/token"

    def test_get_parameter_user_info_url(self):
        """Test getting parameter for user info URL"""
        param = ExternalAuthIdentityProviderParameter(
            user_info_url="https://auth.example.com/userinfo"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "UserInfoUrl"
        assert result["parameterName"] == "UserInfoUrl"
        assert result["parameterValue"] == "https://auth.example.com/userinfo"

    def test_get_parameter_client_authentication(self):
        """Test getting parameter for client authentication"""
        param = ExternalAuthIdentityProviderParameter(
            client_authentication="ClientSecretBasic"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "ClientAuthentication"
        assert result["parameterName"] == "ClientAuthentication"
        assert result["parameterValue"] == "ClientSecretBasic"

    def test_get_parameter_custom_parameter(self):
        """Test getting custom parameter"""
        custom_param = ExtParameter(name="scope", value="openid profile")
        param = ExternalAuthIdentityProviderParameter(custom_parameter=custom_param)
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "CustomParameter"
        assert result["parameterName"] == "scope"
        assert result["parameterValue"] == "openid profile"

    def test_get_parameter_identity_provider_option(self):
        """Test getting identity provider option"""
        option = ExtParameter(name="PkceEnabled", value="true")
        param = ExternalAuthIdentityProviderParameter(identity_provider_option=option)
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "IdentityProviderOptions"
        assert result["parameterName"] == "PkceEnabled"
        assert result["parameterValue"] == "true"

    def test_get_parameter_jwks_url(self):
        """Test getting parameter for JWKS URL"""
        param = ExternalAuthIdentityProviderParameter(
            jwks_url="https://auth.example.com/.well-known/jwks.json"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "JwksUrl"
        assert result["parameterName"] == "JwksUrl"
        assert (
            result["parameterValue"] == "https://auth.example.com/.well-known/jwks.json"
        )

    def test_get_parameter_issuer_url(self):
        """Test getting parameter for issuer URL"""
        param = ExternalAuthIdentityProviderParameter(
            issuer_url="https://auth.example.com"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "IssuerUrl"
        assert result["parameterName"] == "IssuerUrl"
        assert result["parameterValue"] == "https://auth.example.com"

    def test_get_parameter_custom_parameter_with_sequence_number(self):
        """Test getting custom parameter with sequence number"""
        custom_param = ExtParameter(
            name="scope", value="openid profile", sequence_number=5
        )
        param = ExternalAuthIdentityProviderParameter(custom_parameter=custom_param)
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterType"] == "CustomParameter"
        assert result["parameterName"] == "scope"
        assert result["parameterValue"] == "openid profile"
        assert result["sequenceNumber"] == 5

    def test_get_credential(self):
        """Test getting credential"""
        cred = ExternalAuthIdentityProviderCredential(
            name="test-cred", client_id="client123", client_secret="secret456"
        )
        param = ExternalAuthIdentityProviderParameter(credential=cred)
        result = param.get_credential("TestProvider")
        assert result["credentials"] is not None
        assert len(result["credentials"]) == 2
        client_id_cred = next(
            c for c in result["credentials"] if c["credentialName"] == "clientId"
        )
        client_secret_cred = next(
            c for c in result["credentials"] if c["credentialName"] == "clientSecret"
        )
        assert client_id_cred["credentialValue"] == "client123"
        assert client_secret_cred["credentialValue"] == "secret456"

    def test_get_credential_none(self):
        """Test getting credential when none is set"""
        param = ExternalAuthIdentityProviderParameter(
            authorize_url="https://auth.example.com/authorize"
        )
        result = param.get_credential("TestProvider")
        assert result is None


class TestTransformExternalAuthIdentityProviderParameter:
    """Test TransformExternalAuthIdentityProviderParameter model"""

    def test_transform_parameter_value(self):
        """Test transforming parameter value from environment variable"""
        os.environ["TEST_AUTH_URL"] = "https://auth.example.com/authorize"
        param = TransformExternalAuthIdentityProviderParameter(
            authorize_url="TEST_AUTH_URL"
        )
        result = param.get_external_auth_identity_provider_parameter()
        assert result["parameterValue"] == "https://auth.example.com/authorize"
        del os.environ["TEST_AUTH_URL"]

    def test_transform_credential(self):
        """Test transforming credential from environment variables"""
        os.environ["TEST_CLIENT_ID"] = "client123"
        os.environ["TEST_CLIENT_SECRET"] = "secret456"
        cred = ExternalAuthIdentityProviderCredential(
            name="test-cred",
            client_id="TEST_CLIENT_ID",
            client_secret="TEST_CLIENT_SECRET",
        )
        param = TransformExternalAuthIdentityProviderParameter(credential=cred)
        result = param.get_credential("TestProvider")
        assert result["credentials"] is not None
        assert len(result["credentials"]) == 2
        client_id_cred = next(
            c for c in result["credentials"] if c["credentialName"] == "clientId"
        )
        client_secret_cred = next(
            c for c in result["credentials"] if c["credentialName"] == "clientSecret"
        )
        assert client_id_cred["credentialValue"] == "client123"
        assert client_secret_cred["credentialValue"] == "secret456"
        del os.environ["TEST_CLIENT_ID"]
        del os.environ["TEST_CLIENT_SECRET"]

    def test_transform_credential_none(self):
        """Test transforming when credential returns None"""
        param = TransformExternalAuthIdentityProviderParameter(authorize_url="TEST_URL")
        result = param.get_credential("TestProvider")
        assert result is None


class TestUpdateExternalAuthIdentityProvider:
    """Test UpdateExternalAuthIdentityProvider task"""

    @responses.activate
    def test_run_task_success(self):
        """Test successful task execution"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://old.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        task()

    @responses.activate
    def test_run_task_not_found(self):
        """Test task execution when provider is not found"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "NonExistentProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response with no results
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={"size": 0, "records": []},
            status=200,
        )

        with pytest.raises(
            SalesforceDXException,
            match="External auth identity provider 'NonExistentProvider' not found",
        ):
            task()

    @responses.activate
    def test_run_task_with_namespace(self):
        """Test task execution with namespace"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "namespace": "testns",
                "parameters": [
                    {
                        "token_url": "https://auth.example.com/token",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "TokenUrl",
                            "parameterName": "TokenUrl",
                            "parameterValue": "https://old.example.com/token",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        task()

        # Verify query includes namespace (URL encoded)
        assert "NamespacePrefix" in responses.calls[0].request.url
        assert "testns" in responses.calls[0].request.url

    @responses.activate
    def test_run_task_retrieve_error(self):
        """Test task execution when retrieve fails"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider with error
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to retrieve external auth identity provider object for 'TestProvider'",
        ):
            task()

    @responses.activate
    def test_run_task_update_error(self):
        """Test task execution when update fails"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://old.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider with error
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={"error": "Update failed"},
            status=400,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to update external auth identity provider object for 'TestProvider'",
        ):
            task()

    @responses.activate
    def test_run_task_with_credential_update(self):
        """Test task execution with credential update"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "credential": {
                            "name": "TestCred",
                            "client_id": "client123",
                            "client_secret": "secret456",
                        }
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://auth.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        # Mock get credential
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/named-credentials/external-auth-identity-provider-credentials/TestProvider",
            json={
                "externalAuthIdentityProvider": "TestProvider",
                "credentials": None,
            },
            status=200,
        )

        # Mock update credential
        responses.add(
            method=responses.POST,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/named-credentials/external-auth-identity-provider-credentials/TestProvider",
            json={},
            status=200,
        )

        task()

    @responses.activate
    def test_run_task_with_multiple_parameters(self):
        """Test task execution with multiple parameters"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    },
                    {
                        "token_url": "https://auth.example.com/token",
                    },
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://old.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        task()

    @responses.activate
    def test_run_task_with_transform_parameters(self):
        """Test task execution with transform parameters"""
        os.environ["TEST_AUTH_URL"] = "https://auth.example.com/authorize"

        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "transform_parameters": [
                    {
                        "authorize_url": "TEST_AUTH_URL",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://old.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        task()

        del os.environ["TEST_AUTH_URL"]

    @responses.activate
    def test_run_task_query_exception(self):
        """Test task execution when query raises exception"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response with exception
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            body=Exception("Query failed"),
        )

        with pytest.raises(
            SalesforceDXException,
            match="External auth identity provider 'TestProvider' not found",
        ):
            task()

    @responses.activate
    def test_run_task_retrieve_exception(self):
        """Test task execution when retrieve raises exception"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider with exception
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            body=Exception("Retrieve failed"),
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to retrieve external auth identity provider object for 'TestProvider'",
        ):
            task()

    @responses.activate
    def test_run_task_add_new_parameter_to_empty_list(self):
        """Test adding parameter when no parameters exist"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "authorize_url": "https://auth.example.com/authorize",
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider with no parameters
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={"Metadata": {"externalAuthIdentityProviderParameters": []}},
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        task()

    @responses.activate
    def test_run_task_credential_update_failure(self):
        """Test task execution when credential update fails"""
        task = create_task(
            UpdateExternalAuthIdentityProvider,
            {
                "name": "TestProvider",
                "parameters": [
                    {
                        "credential": {
                            "name": "TestCred",
                            "client_id": "client123",
                            "client_secret": "secret456",
                        }
                    }
                ],
            },
        )

        # Mock query response
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "0soxx0000000001AAA"}],
            },
            status=200,
        )

        # Mock get external auth identity provider
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={
                "Metadata": {
                    "externalAuthIdentityProviderParameters": [
                        {
                            "parameterType": "AuthorizeUrl",
                            "parameterName": "AuthorizeUrl",
                            "parameterValue": "https://auth.example.com/authorize",
                        }
                    ]
                }
            },
            status=200,
        )

        # Mock update external auth identity provider
        responses.add(
            method=responses.PATCH,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling/sobjects/ExternalAuthIdentityProvider/0soxx0000000001AAA",
            json={},
            status=200,
        )

        # Mock get credential
        responses.add(
            method=responses.GET,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/named-credentials/external-auth-identity-provider-credentials/TestProvider",
            json={
                "externalAuthIdentityProvider": "TestProvider",
                "credentials": None,
            },
            status=200,
        )

        # Mock update credential failure
        responses.add(
            method=responses.POST,
            url=f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/named-credentials/external-auth-identity-provider-credentials/TestProvider",
            json={"error": "Credential update failed"},
            status=400,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Failed to update credentials for external auth identity provider 'TestProvider'",
        ):
            task()
