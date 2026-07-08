export function pickDefaultColumns(columns) {
  if (!columns?.length) return []
  const emailColumn = columns.find((col) => /email/i.test(col))
  return emailColumn ? [emailColumn] : [columns[0]]
}
