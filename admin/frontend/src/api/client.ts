export type ApiResult<T> = { success: true; data?: T } | { success: false; error: string }

// The same UI is served by both processes. Local browser operations are only
// available from the client process listening on port 9005.
export const isClientProcess = typeof window !== 'undefined' && window.location.port === '9005'
export const clientProcessMessage = '该操作需要在客户端 9005 中进行，请打开客户端后重试'

export async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const result = await response.json() as ApiResult<T>
  if (!result.success) throw new Error(result.error || '请求失败')
  return result.data as T
}

export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(path, { method: 'POST', body: form })
  const result = await response.json() as ApiResult<T>
  if (!result.success) throw new Error(result.error || '请求失败')
  return result.data as T
}

export function query(path: string, params: Record<string, string | number>): string {
  return `${path}?${new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)]))}`
}
