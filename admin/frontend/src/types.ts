export type Kernel = 'chrome' | 'firefox'
export type Page<T> = { items: T[]; total: number; page: number; page_size: number; total_pages: number }
export type Proxy = {
  code: string; proxy_name: string; proxy_type: 'http' | 'https' | 'socks5';
  proxy_addr: string; proxy_port: number; proxy_input_type: 'manual' | 'api';
  proxy_api_url?: string; username?: string; password?: string; remark?: string;
  create_time?: string
}
export type Environment = {
  code: string; name: string; platform: string; browser_version: string; browser_kernel: Kernel;
  user_agent: string; proxy_ip_code: string | null; status: 'running' | 'stopped';
  pid: number | null; debug_port: number | null; remark: string; create_time: string;
  open_home_page: boolean; enable_tabs: boolean; tabs?: string; launch_args?: string; cookie?: string;
  proxy_mode?: 'no_proxy' | 'existing' | 'custom'; proxy_code?: string;
  custom_proxy_type?: string; custom_proxy_addr?: string; custom_proxy_port?: number;
  custom_proxy_username?: string; custom_proxy_password?: string;
  proxy_input_type?: string; proxy_api_url?: string; fingerprint?: Record<string, any>
}
export type KernelCatalog = Record<Kernel, { default_version: string; versions: string[]; installed_versions: string[] }>
export type BrowserSettings = { browser_app_data_dir: string; is_default: boolean; valid: boolean;
  checks: Record<string, boolean>; kernels: KernelCatalog; missing_versions: string[] }
export type SettingsCapabilities = { process_role: 'client'; local_settings: boolean; kernel_management: boolean; token_update: boolean }
export type OpenResult = { pid: number; debug_port: number | null; browser_kernel: Kernel;
  debug_protocol: string | null; debug_endpoint: string | null }
export type Extension = { code: string; name: string; version: string; browser_kernel: Kernel; extension_type: 'builtin'|'normal'; provider?: string; source_url?: string; description?: string; status: number; environment_codes: string[] }
