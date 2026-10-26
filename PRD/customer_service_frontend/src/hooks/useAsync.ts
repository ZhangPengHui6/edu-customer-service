import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DependencyList,
} from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: (silent?: boolean) => Promise<void>
  setData: (value: T | null) => void
}

export function useAsync<T>(
  loader: () => Promise<T>,
  deps: DependencyList = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const loaderRef = useRef(loader)
  const requestId = useRef(0)

  useEffect(() => {
    loaderRef.current = loader
  }, [loader])

  const reload = useCallback(async (silent = false) => {
    const id = requestId.current + 1
    requestId.current = id
    if (!silent) setLoading(true)
    try {
      const result = await loaderRef.current()
      if (requestId.current === id) {
        setData(result)
        setError(null)
      }
    } catch (cause) {
      if (requestId.current === id) {
        setError(cause instanceof Error ? cause.message : '加载失败')
      }
    } finally {
      if (requestId.current === id) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
    // Loader identity is intentionally ignored; callers pass explicit deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, loading, error, reload, setData }
}

export function usePolling(
  callback: () => Promise<void> | void,
  delayMs: number,
  enabled = true,
): void {
  const callbackRef = useRef(callback)
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return
    let stopped = false
    let timer = 0
    const tick = async () => {
      try {
        await callbackRef.current()
      } finally {
        if (!stopped) timer = window.setTimeout(tick, delayMs)
      }
    }
    timer = window.setTimeout(tick, delayMs)
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [delayMs, enabled])
}
