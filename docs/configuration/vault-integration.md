# Secure Configuration Management with HashiCorp Vault

`pytest-analyzer` supports integrating with HashiCorp Vault to securely manage sensitive configuration data like API keys, tokens, and other credentials. This approach avoids storing secrets in plaintext in configuration files or environment variables.

## Features

- **Centralized Secret Management**: Store all sensitive data in a secure, centralized Vault instance.
- **Dynamic Secret Retrieval**: The application fetches secrets at runtime, so they are never stored on disk.
- **Multiple Authentication Methods**: Supports authentication via Vault Token and AppRole.
- **Secret Caching**: In-memory caching with a configurable TTL reduces requests to Vault and improves performance.
- **Auditing**: All secret access attempts are logged for security and monitoring purposes.
- **KVv2 Versioning**: Supports retrieving specific versions of secrets from Vault's Key-Value v2 secrets engine.

## How It Works

When Vault integration is enabled, the `ConfigurationManager` scans the entire configuration structure for string values that follow a specific Vault URI format. When a URI is found, it uses the `VaultSecretManager` to connect to Vault, authenticate, and fetch the corresponding secret value. This value then replaces the URI in the configuration before it is passed to the Pydantic `Settings` model for validation.

If the connection to Vault fails or a secret cannot be retrieved, an error is logged, and the URI string is left in place, which will likely cause a validation error downstream, preventing the application from starting with an incomplete configuration.

## Configuration

To enable Vault integration, you need to configure the `vault` section in your `pytest-analyzer.yaml` file or via environment variables.

### Vault Settings

The following settings are available under the `vault` configuration block:

| Setting             | Type      | Environment Variable (`PYTEST_ANALYZER_VAULT_...`) | Description                                                                                             |
| ------------------- | --------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `enabled`           | `boolean` | `ENABLED`                                          | **Required**. Set to `true` to enable Vault integration.                                                |
| `url`               | `string`  | `URL`                                              | **Required**. The full URL of your Vault server (e.g., `https://vault.example.com:8200`).               |
| `auth_method`       | `string`  | `AUTH_METHOD`                                      | The authentication method to use. Can be `token` or `approle`. Default: `token`.                        |
| `token`             | `string`  | `TOKEN`                                            | The Vault token to use for authentication. **Required** if `auth_method` is `token`.                    |
| `role_id`           | `string`  | `ROLE_ID`                                          | The RoleID for AppRole authentication. **Required** if `auth_method` is `approle`.                      |
| `secret_id`         | `string`  | `SECRET_ID`                                        | The SecretID for AppRole authentication. **Required** if `auth_method` is `approle`.                    |
| `mount_point`       | `string`  | `MOUNT_POINT`                                      | The mount point of the KV secrets engine in Vault. Default: `secret`.                                   |
| `cache_ttl`         | `integer` | `CACHE_TTL`                                        | Time-to-live for cached secrets in seconds. Set to `0` to disable caching. Default: `300`.              |
| `timeout`           | `integer` | `TIMEOUT`                                          | Timeout for Vault client requests in seconds. Default: `30`.                                            |
| `unwrap_cubbyhole`  | `boolean` | `UNWRAP_CUBBYHOLE`                                 | For AppRole, set to `true` if the SecretID is response-wrapped. Default: `false`.                       |

### Example Configuration (`pytest-analyzer.yaml`)

#### Using Token Authentication
