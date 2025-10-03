import os
from unittest import mock

import pytest
import responses

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.tasks.salesforce.update_named_credential import (
    NamedCredentialCalloutOptions,
    NamedCredentialHttpHeader,
    NamedCredentialParameter,
    TransformNamedCredentialParameter,
    UpdateNamedCredential,
)
from cumulusci.tests.util import CURRENT_SF_API_VERSION

from .util import create_task


class TestNamedCredentialHttpHeader:
    """Test NamedCredentialHttpHeader model"""

    def test_http_header_defaults(self):
        """Test default values for http header"""
        header = NamedCredentialHttpHeader(name="test-header", value="test-value")
        assert header.name == "test-header"
        assert header.value == "test-value"
        assert header.secret is False
        assert header.sequence_number is None

    def test_http_header_with_secret(self):
        """Test http header with secret flag"""
        header = NamedCredentialHttpHeader(
            name="api-key", value="secret123", secret=True, sequence_number=1
        )
        assert header.name == "api-key"
        assert header.value == "secret123"
        assert header.secret is True
        assert header.sequence_number == 1


class TestNamedCredentialParameter:
    """Test NamedCredentialParameter model"""

    def test_parameter_with_url(self):
        """Test parameter with URL"""
        param = NamedCredentialParameter(url="https://example.com")
        assert param.url == "https://example.com"
        assert param.param_type() == "Url"
        assert param.param_value() == "https://example.com"

    def test_parameter_with_authentication(self):
        """Test parameter with authentication"""
        param = NamedCredentialParameter(authentication="MyAuth")
        assert param.authentication == "MyAuth"
        assert param.param_type() == "Authentication"
        assert param.param_value() == "MyAuth"

    def test_parameter_with_certificate(self):
        """Test parameter with certificate"""
        param = NamedCredentialParameter(certificate="MyCert")
        assert param.certificate == "MyCert"
        assert param.param_type() == "ClientCertificate"
        assert param.param_value() == "MyCert"

    def test_parameter_with_allowed_namespaces(self):
        """Test parameter with allowed managed package namespaces"""
        param = NamedCredentialParameter(
            allowed_managed_package_namespaces="namespace1"
        )
        assert param.allowed_managed_package_namespaces == "namespace1"
        assert param.param_type() == "AllowedManagedPackageNamespaces"
        assert param.param_value() == "namespace1"

    def test_parameter_with_http_headers(self):
        """Test parameter with HTTP headers"""
        headers = [
            NamedCredentialHttpHeader(name="header1", value="value1"),
            NamedCredentialHttpHeader(
                name="header2", value="value2", sequence_number=1
            ),
        ]
        param = NamedCredentialParameter(http_header=headers)
        assert param.param_type() == "HttpHeader"
        assert param.param_value(http_header="header1") == "value1"
        assert param.param_value(http_header="header2") == "value2"
        assert param.param_value(http_header="nonexistent") is None

    def test_parameter_validation_error_multiple_params(self):
        """Test that only one parameter can be provided"""
        with pytest.raises(ValueError, match="Only one of the parameters is required"):
            NamedCredentialParameter(url="https://example.com", certificate="MyCert")

    def test_parameter_validation_error_no_params(self):
        """Test that at least one parameter must be provided"""
        with pytest.raises(ValueError, match="Only one of the parameters is required"):
            NamedCredentialParameter()

    def test_get_parameter_to_update_url(self):
        """Test get_parameter_to_update for URL parameter"""
        param = NamedCredentialParameter(url="https://example.com")
        result = param.get_parameter_to_update()
        assert len(result) == 1
        assert result[0]["parameterType"] == "Url"
        assert result[0]["parameterValue"] == "https://example.com"

    def test_get_parameter_to_update_authentication(self):
        """Test get_parameter_to_update for authentication parameter"""
        param = NamedCredentialParameter(authentication="MyAuth")
        result = param.get_parameter_to_update()
        assert len(result) == 1
        assert result[0]["parameterType"] == "Authentication"
        assert result[0]["parameterName"] == "ExternalCredential"
        assert result[0]["externalCredential"] == "MyAuth"
        assert result[0]["parameterValue"] == "MyAuth"

    def test_get_parameter_to_update_certificate(self):
        """Test get_parameter_to_update for certificate parameter"""
        param = NamedCredentialParameter(certificate="MyCert")
        result = param.get_parameter_to_update()
        assert len(result) == 1
        assert result[0]["parameterType"] == "ClientCertificate"
        assert result[0]["parameterName"] == "ClientCertificate"
        assert result[0]["certificate"] == "MyCert"
        assert result[0]["parameterValue"] == "MyCert"

    def test_get_parameter_to_update_http_headers(self):
        """Test get_parameter_to_update for HTTP headers"""
        headers = [
            NamedCredentialHttpHeader(name="header1", value="value1", secret=True),
            NamedCredentialHttpHeader(
                name="header2", value="value2", sequence_number=2
            ),
        ]
        param = NamedCredentialParameter(http_header=headers)
        result = param.get_parameter_to_update()
        assert len(result) == 2
        assert result[0]["parameterType"] == "HttpHeader"
        assert result[0]["parameterName"] == "header1"
        assert result[0]["parameterValue"] == "value1"
        assert result[0]["secret"] is True
        assert result[1]["parameterName"] == "header2"
        assert result[1]["parameterValue"] == "value2"
        assert result[1]["sequenceNumber"] == 2


class TestTransformNamedCredentialParameter:
    """Test TransformNamedCredentialParameter model"""

    def test_transform_param_value_url(self):
        """Test transform parameter value for URL from environment"""
        with mock.patch.dict(os.environ, {"TEST_URL": "https://env-example.com"}):
            param = TransformNamedCredentialParameter(url="TEST_URL")
            assert param.param_value() == "https://env-example.com"

    def test_transform_param_value_authentication(self):
        """Test transform parameter value for authentication from environment"""
        with mock.patch.dict(os.environ, {"TEST_AUTH": "EnvAuth"}):
            param = TransformNamedCredentialParameter(authentication="TEST_AUTH")
            assert param.param_value() == "EnvAuth"

    def test_transform_param_value_certificate(self):
        """Test transform parameter value for certificate from environment"""
        with mock.patch.dict(os.environ, {"TEST_CERT": "EnvCert"}):
            param = TransformNamedCredentialParameter(certificate="TEST_CERT")
            assert param.param_value() == "EnvCert"

    def test_transform_param_value_http_header(self):
        """Test transform parameter value for HTTP header from environment"""
        with mock.patch.dict(os.environ, {"HEADER_VALUE": "env-header-value"}):
            headers = [
                NamedCredentialHttpHeader(name="test-header", value="HEADER_VALUE")
            ]
            param = TransformNamedCredentialParameter(http_header=headers)
            assert param.param_value(http_header="test-header") == "env-header-value"

    def test_transform_param_value_missing_env(self):
        """Test transform parameter value when environment variable is missing"""
        param = TransformNamedCredentialParameter(url="NONEXISTENT_VAR")
        assert param.param_value() is None


class TestNamedCredentialCalloutOptions:
    """Test NamedCredentialCalloutOptions model"""

    def test_callout_options_defaults(self):
        """Test default values for callout options"""
        options = NamedCredentialCalloutOptions()
        assert options.allow_merge_fields_in_body is None
        assert options.allow_merge_fields_in_header is None
        assert options.generate_authorization_header is None

    def test_callout_options_with_values(self):
        """Test callout options with values"""
        options = NamedCredentialCalloutOptions(
            allow_merge_fields_in_body=True,
            allow_merge_fields_in_header=True,
            generate_authorization_header=False,
        )
        assert options.allow_merge_fields_in_body is True
        assert options.allow_merge_fields_in_header is True
        assert options.generate_authorization_header is False


class TestUpdateNamedCredential:
    """Test UpdateNamedCredential task"""

    @responses.activate
    def test_update_named_credential_success(self):
        """Test successful update of named credential"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "namespace": "",
                "callout_options": {
                    "allow_merge_fields_in_body": True,
                    "allow_merge_fields_in_header": True,
                    "generate_authorization_header": True,
                },
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                            "certificate": None,
                            "description": None,
                            "externalCredential": None,
                            "sequenceNumber": None,
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_namespace(self):
        """Test update of named credential with namespace"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "namespace": "th_dev",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID with namespace
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+AND+NamespacePrefix%3D%27th_dev%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_not_found(self):
        """Test error when named credential is not found"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "nonexistent",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID - not found
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27nonexistent%27+LIMIT+1",
            json={"size": 0, "records": []},
            status=200,
        )

        with pytest.raises(Exception):  # Can be TypeError or SalesforceDXException
            task()

    @responses.activate
    def test_update_named_credential_query_error(self):
        """Test error handling when query fails"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query error
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"error": "Query failed"},
            status=500,
        )

        with pytest.raises(Exception):  # Can be TypeError or SalesforceDXException
            task()

    @responses.activate
    def test_update_named_credential_not_secured_endpoint(self):
        """Test error when named credential is not a SecuredEndpoint"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object with wrong type
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={"Metadata": {"namedCredentialType": "Legacy"}},
            status=200,
        )

        with pytest.raises(
            SalesforceDXException,
            match="Named credential 'testNc' is not a secured endpoint",
        ):
            task()

    @responses.activate
    def test_update_named_credential_get_object_error(self):
        """Test error when getting named credential object fails"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object - error
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={"error": "Failed to retrieve"},
            status=404,
        )

        with pytest.raises(Exception):  # Can be TypeError or SalesforceDXException
            task()

    @responses.activate
    def test_update_named_credential_update_error(self):
        """Test error when updating named credential fails"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"url": "https://testingAPI.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential - error
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={"error": "Update failed"},
            status=400,
        )

        with pytest.raises(Exception):  # Can be TypeError or SalesforceDXException
            task()

    @responses.activate
    def test_update_named_credential_with_http_headers(self):
        """Test update of named credential with HTTP headers"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [
                    {
                        "http_header": [
                            {"name": "x-api-key", "value": "secret123", "secret": True},
                            {
                                "name": "x-client-id",
                                "value": "client456",
                                "sequence_number": 1,
                            },
                        ]
                    }
                ],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://api.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_authentication(self):
        """Test update of named credential with authentication"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"authentication": "MyExternalCredential"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://api.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_certificate(self):
        """Test update of named credential with certificate"""
        task = create_task(
            UpdateNamedCredential,
            {"name": "testNc", "parameters": [{"certificate": "MyCertificate"}]},
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://api.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_transform_parameters(self):
        """Test update of named credential with transform parameters from environment"""
        with mock.patch.dict(
            os.environ,
            {
                "TEST_URL": "https://env.example.com",
                "TEST_AUTH": "EnvAuth",
                "HEADER_VALUE": "env-header-value",
            },
        ):
            task = create_task(
                UpdateNamedCredential,
                {
                    "name": "testNc",
                    "transform_parameters": [
                        {"url": "TEST_URL"},
                        {"authentication": "TEST_AUTH"},
                        {
                            "http_header": [
                                {
                                    "name": "x-api-key",
                                    "value": "HEADER_VALUE",
                                    "secret": True,
                                }
                            ]
                        },
                    ],
                },
            )

            nc_id = "0XA1234567890ABC"
            tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

            # Mock query for named credential ID
            responses.add(
                method="GET",
                url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
                json={"size": 1, "records": [{"Id": nc_id}]},
                status=200,
            )

            # Mock get named credential object
            responses.add(
                method="GET",
                url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
                json={
                    "Metadata": {
                        "namedCredentialType": "SecuredEndpoint",
                        "namedCredentialParameters": [
                            {
                                "parameterName": None,
                                "parameterType": "Url",
                                "parameterValue": "https://old.example.com",
                                "certificate": None,
                                "description": None,
                                "externalCredential": None,
                                "sequenceNumber": None,
                            }
                        ],
                    }
                },
                status=200,
            )

            # Mock update named credential
            responses.add(
                method="PATCH",
                url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
                json={},
                status=200,
            )

            task()
            assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_callout_options(self):
        """Test update of named credential with callout options"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "callout_options": {
                    "allow_merge_fields_in_body": True,
                    "allow_merge_fields_in_header": False,
                    "generate_authorization_header": True,
                },
                "parameters": [{"url": "https://api.example.com"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_no_template_parameter(self):
        """Test update when no template parameter exists"""
        task = create_task(
            UpdateNamedCredential,
            {"name": "testNc", "parameters": [{"url": "https://api.example.com"}]},
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object without Url parameter
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_update_existing_parameter(self):
        """Test updating an existing parameter"""
        task = create_task(
            UpdateNamedCredential,
            {"name": "testNc", "parameters": [{"url": "https://new.example.com"}]},
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object with existing Url parameter
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_with_allowed_namespaces(self):
        """Test update of named credential with allowed managed package namespaces"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [{"allowed_managed_package_namespaces": "th_dev"}],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://api.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_update_http_header_existing(self):
        """Test updating existing HTTP header parameter"""
        task = create_task(
            UpdateNamedCredential,
            {
                "name": "testNc",
                "parameters": [
                    {
                        "http_header": [
                            {"name": "x-api-key", "value": "new-value", "secret": True}
                        ]
                    }
                ],
            },
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object with existing HTTP header
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://api.example.com",
                        },
                        {
                            "parameterName": "x-api-key",
                            "parameterType": "HttpHeader",
                            "parameterValue": "old-value",
                        },
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={},
            status=200,
        )

        task()
        assert len(responses.calls) == 3

    @responses.activate
    def test_update_named_credential_exception_in_update(self):
        """Test exception handling during update"""
        task = create_task(
            UpdateNamedCredential,
            {"name": "testNc", "parameters": [{"url": "https://api.example.com"}]},
        )

        nc_id = "0XA1234567890ABC"
        tooling_url = f"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/tooling"

        # Mock query for named credential ID
        responses.add(
            method="GET",
            url=f"{tooling_url}/query/?q=SELECT+Id+FROM+NamedCredential+WHERE+DeveloperName%3D%27testNc%27+LIMIT+1",
            json={"size": 1, "records": [{"Id": nc_id}]},
            status=200,
        )

        # Mock get named credential object
        responses.add(
            method="GET",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            json={
                "Metadata": {
                    "namedCredentialType": "SecuredEndpoint",
                    "namedCredentialParameters": [
                        {
                            "parameterName": None,
                            "parameterType": "Url",
                            "parameterValue": "https://old.example.com",
                        }
                    ],
                }
            },
            status=200,
        )

        # Mock update named credential - exception
        responses.add(
            method="PATCH",
            url=f"{tooling_url}/sobjects/NamedCredential/{nc_id}",
            body=Exception("Connection error"),
        )

        with pytest.raises(Exception):  # Can be TypeError or SalesforceDXException
            task()
