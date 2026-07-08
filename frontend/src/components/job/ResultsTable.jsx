import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TablePagination from '@mui/material/TablePagination'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'

export default function ResultsTable({
  results,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  loading,
  error,
}) {
  if (error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    )
  }

  if (!results && loading) {
    return (
      <Paper sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    )
  }

  if (!results) return null

  const { columns = [], rows = [], total_rows: totalRows = 0 } = results
  const pageIndex = page - 1

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="overline" color="primary">
            Step 4
          </Typography>
          <Typography variant="h6">Processed data</Typography>
          <Typography variant="body2" color="text.secondary">
            {totalRows === 0
              ? results.message || 'No rows in result set'
              : `${totalRows.toLocaleString()} total rows`}
          </Typography>
        </Box>

        {totalRows === 0 ? (
          <Alert severity="info">
            {results.message || 'The job completed but returned no data rows.'}
          </Alert>
        ) : (
          <>
            <TableContainer sx={{ maxHeight: 480, border: 1, borderColor: 'divider', borderRadius: 2 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    {columns.map((column) => (
                      <TableCell key={column}>{column}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row, index) => (
                    <TableRow key={`${page}-${index}`} hover>
                      {columns.map((column) => (
                        <TableCell key={column}>{row[column] ?? ''}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              component="div"
              count={totalRows}
              page={pageIndex}
              rowsPerPage={pageSize}
              onPageChange={(_, newPage) => onPageChange(newPage + 1)}
              onRowsPerPageChange={(event) => onPageSizeChange(Number(event.target.value))}
              rowsPerPageOptions={[25, 50, 100, 200]}
              disabled={loading}
            />
          </>
        )}

        {loading && (
          <Typography variant="body2" color="text.secondary">
            Refreshing page…
          </Typography>
        )}
      </Stack>
    </Paper>
  )
}
