const SERVER_URL_KEY = 'deskflow_server_url'

export function getServerUrl(): string {
  return localStorage.getItem(SERVER_URL_KEY) || ''
}

export function setServerUrl(url: string): void {
  localStorage.setItem(SERVER_URL_KEY, url)
}

export function api(path: string): string {
  const base = getServerUrl()
  return base ? `${base}${path}` : path
}
