export function formatDateTime(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRowProgress(rowsProcessed, totalRows) {
  if (totalRows == null) return null
  const processed = rowsProcessed ?? 0
  return `${processed.toLocaleString()} / ${totalRows.toLocaleString()} rows`
}
