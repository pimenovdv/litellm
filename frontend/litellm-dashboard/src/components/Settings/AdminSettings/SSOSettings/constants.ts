import googleLogo from "../../../../../public/assets/logos/google.svg";
import microsoftAzureLogo from "../../../../../public/assets/logos/microsoft_azure.svg";

/**
 * Map of SSO Provider identifiers to their respective logo URLs.
 * @type {Record<string, string>}
 */
export const ssoProviderLogoMap: Record<string, string> = {
  google: googleLogo.src,
  microsoft: microsoftAzureLogo.src,
  okta: "https://www.okta.com/sites/default/files/Okta_Logo_BrightBlue_Medium.png",
  generic: "",
  saml: "",
};

/**
 * Map of SSO Provider identifiers to their display names.
 * Used consistently across dropdowns and tables.
 * @type {Record<string, string>}
 */
export const ssoProviderDisplayNames: Record<string, string> = {
  google: "Google SSO",
  microsoft: "Microsoft SSO",
  okta: "Okta / Auth0 SSO",
  generic: "Generic SSO",
  saml: "SAML SSO",
};

/**
 * Map of internal role identifiers to their human-readable display names.
 * @type {Record<string, string>}
 */
export const defaultRoleDisplayNames: Record<string, string> = {
  internal_user_viewer: "Internal Viewer",
  internal_user: "Internal User",
  proxy_admin_viewer: "Proxy Admin Viewer",
  proxy_admin: "Proxy Admin",
};
