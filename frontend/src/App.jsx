import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined'
import Box from '@mui/material/Box'
import Container from '@mui/material/Container'
import Drawer from '@mui/material/Drawer'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import { useCallback, useEffect, useState } from 'react'
import { cancelJob, getJobResults, getJobStatus, invokeTransform } from './api/jobs'
import { getUploadData, getUploadStatus, listUploads, uploadFile } from './api/uploads'
import { queryKeys } from './api/queryKeys'
import ErrorAlert from './components/common/ErrorAlert'
import JobProgressPanel from './components/job/JobProgressPanel'
import ResultsTable from './components/job/ResultsTable'
import FileSidebar from './components/layout/FileSidebar'
import TransformForm from './components/transform/TransformForm'
import FileDataPreview from './components/upload/FileDataPreview'
import FileUploadPanel from './components/upload/FileUploadPanel'
import {
  TERMINAL_JOB_STATUSES,
  TRANSFORM_TYPES,
} from './constants/transformTypes'
import { pickDefaultColumns } from './utils/columns'

const SIDEBAR_WIDTH = 360
const INITIAL_UPLOAD_STATE = { phase: 'idle' }

export default function App() {
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))
  const queryClient = useQueryClient()

  const [uploadState, setUploadState] = useState(INITIAL_UPLOAD_STATE)
  const [activeFileId, setActiveFileId] = useState(null)
  const [activeJobId, setActiveJobId] = useState(null)
  const [isNewUploadMode, setIsNewUploadMode] = useState(true)
  const [submitError, setSubmitError] = useState(null)

  const [transformType, setTransformType] = useState(TRANSFORM_TYPES.REGEX_REPLACE)
  const [naturalLanguagePrompt, setNaturalLanguagePrompt] = useState(
    'Find email addresses and replace them with REDACTED',
  )
  const [replacementValue, setReplacementValue] = useState('REDACTED')
  const [selectedColumns, setSelectedColumns] = useState([])

  const [resultsPage, setResultsPage] = useState(1)
  const [resultsPageSize, setResultsPageSize] = useState(50)

  const [previewPage, setPreviewPage] = useState(1)
  const [previewPageSize, setPreviewPageSize] = useState(50)

  const uploadsQuery = useQuery({
    queryKey: queryKeys.uploads.all,
    queryFn: listUploads,
    refetchInterval: 3000,
  })

  const uploadStatusQuery = useQuery({
    queryKey: queryKeys.uploadStatus(activeFileId),
    queryFn: () => getUploadStatus(activeFileId),
    enabled: Boolean(activeFileId) && uploadState.phase === 'processing',
    refetchInterval: 1500,
  })

  useEffect(() => {
    const status = uploadStatusQuery.data
    if (!status || status.status !== 'ready') return

    setUploadState((prev) => ({
      ...prev,
      phase: 'ready',
      columns: status.columns,
      filename: status.filename,
    }))
    setSelectedColumns((prev) =>
      prev.length > 0 ? prev : pickDefaultColumns(status.columns),
    )
  }, [uploadStatusQuery.data])

  useEffect(() => {
    if (!uploadStatusQuery.error) return
    setUploadState((prev) => ({
      ...prev,
      phase: 'error',
      error: uploadStatusQuery.error.message,
    }))
  }, [uploadStatusQuery.error])

  const jobStatusQuery = useQuery({
    queryKey: queryKeys.jobStatus(activeJobId),
    queryFn: () => getJobStatus(activeJobId),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && TERMINAL_JOB_STATUSES.has(status) ? false : 2000
    },
  })

  const job = jobStatusQuery.data ?? null

  const resultsQuery = useQuery({
    queryKey: queryKeys.jobResults(activeJobId, resultsPage, resultsPageSize),
    queryFn: () => getJobResults(activeJobId, resultsPage, resultsPageSize),
    enabled: job?.status === 'SUCCESS' && Boolean(activeJobId),
    placeholderData: keepPreviousData,
  })

  const fileDataQuery = useQuery({
    queryKey: queryKeys.uploadData(activeFileId, previewPage, previewPageSize),
    queryFn: () => getUploadData(activeFileId, previewPage, previewPageSize),
    enabled: uploadState.phase === 'ready' && Boolean(activeFileId),
    placeholderData: keepPreviousData,
  })

  const uploadMutation = useMutation({
    mutationFn: uploadFile,
    onSuccess: (response, file) => {
      const fileId = response.uploaded_file_id
      setActiveFileId(fileId)
      setUploadState({
        phase: 'processing',
        uploadedFileId: fileId,
        filename: file.name,
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all })
    },
    onError: (error, file) => {
      setUploadState({
        phase: 'error',
        filename: file.name,
        error: error.message,
      })
    },
  })

  const transformMutation = useMutation({
    mutationFn: invokeTransform,
    onSuccess: (response) => {
      setActiveJobId(response.job_id)
      queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.jobStatus(response.job_id) })
    },
    onError: (error) => {
      setSubmitError(error.message)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: cancelJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobStatus(activeJobId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all })
    },
    onError: (error) => {
      setSubmitError(error.message)
    },
  })

  const loadFile = useCallback(async (fileId, { preserveJob = false } = {}) => {
    const status = await getUploadStatus(fileId)
    setActiveFileId(fileId)
    setIsNewUploadMode(false)

    if (!preserveJob) {
      setActiveJobId(null)
      setResultsPage(1)
    }

    if (status.status === 'ready') {
      setUploadState({
        phase: 'ready',
        uploadedFileId: fileId,
        filename: status.filename,
        columns: status.columns,
      })
      setSelectedColumns(pickDefaultColumns(status.columns))
      return
    }

    setUploadState({
      phase: 'processing',
      uploadedFileId: fileId,
      filename: status.filename,
    })
    setSelectedColumns([])
  }, [])

  const handleNewUpload = () => {
    setIsNewUploadMode(true)
    setActiveFileId(null)
    setActiveJobId(null)
    setUploadState(INITIAL_UPLOAD_STATE)
    setSubmitError(null)
    setSelectedColumns([])
    setResultsPage(1)
  }

  const handleSelectFile = async (fileId) => {
    setSubmitError(null)
    try {
      await loadFile(fileId)
    } catch (error) {
      setSubmitError(error.message)
    }
  }

  const handleSelectJob = async (jobId, fileId) => {
    setSubmitError(null)
    setResultsPage(1)
    try {
      await loadFile(fileId, { preserveJob: true })
      setActiveJobId(jobId)
      await queryClient.fetchQuery({
        queryKey: queryKeys.jobStatus(jobId),
        queryFn: () => getJobStatus(jobId),
      })
    } catch (error) {
      setSubmitError(error.message)
    }
  }

  const handleFileSelect = (file) => {
    setUploadState({ phase: 'uploading', filename: file.name })
    setActiveJobId(null)
    setSubmitError(null)
    setSelectedColumns([])
    setIsNewUploadMode(true)
    setResultsPage(1)
    setPreviewPage(1)
    uploadMutation.mutate(file)
  }

  const handleSubmit = () => {
    if (!uploadState.uploadedFileId) return

    setSubmitError(null)
    setResultsPage(1)

    const payload = {
      uploaded_file_id: uploadState.uploadedFileId,
      transform_type: transformType,
      natural_language_prompt: naturalLanguagePrompt.trim(),
      target_columns: selectedColumns,
    }

    if (transformType === TRANSFORM_TYPES.REGEX_REPLACE) {
      payload.replacement_value = replacementValue.trim()
    }

    transformMutation.mutate(payload)
  }

  const handleCancel = () => {
    if (!activeJobId) return
    cancelMutation.mutate(activeJobId)
  }

  const showUploadPanel = isNewUploadMode
  const showTransformForm = Boolean(activeFileId)
  const formDisabled = uploadState.phase !== 'ready'

  const sidebar = (
    <FileSidebar
      uploads={uploadsQuery.data ?? []}
      isLoading={uploadsQuery.isLoading}
      activeFileId={activeFileId}
      activeJobId={activeJobId}
      onSelectFile={handleSelectFile}
      onSelectJob={handleSelectJob}
      onNewUpload={handleNewUpload}
    />
  )

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        minHeight: '100vh',
        bgcolor: 'background.default',
      }}
    >
      {isDesktop ? (
        <Drawer
          variant="permanent"
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: SIDEBAR_WIDTH,
              boxSizing: 'border-box',
              position: 'relative',
              height: '100vh',
            },
          }}
          open
        >
          {sidebar}
        </Drawer>
      ) : (
        <Box
          sx={{
            width: '100%',
            maxHeight: { xs: '38vh', md: 'none' },
            overflow: 'auto',
            borderBottom: { xs: 1, md: 0 },
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          {sidebar}
        </Box>
      )}

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0 }}>
        <Toolbar disableGutters sx={{ px: { xs: 2, md: 4 }, py: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AutoFixHighOutlinedIcon color="primary" />
            <Box>
              <Typography variant="h5" component="h1">
                Pattern Matching &amp; Replacement
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Natural language transforms at scale with async Spark processing
              </Typography>
            </Box>
          </Stack>
        </Toolbar>

        <Container maxWidth="lg" sx={{ pb: 6 }}>
          <Stack spacing={3}>
            <ErrorAlert error={submitError} onClose={() => setSubmitError(null)} />

            {showUploadPanel && (
              <FileUploadPanel
                onFileSelect={handleFileSelect}
                disabled={
                  uploadMutation.isPending || uploadState.phase === 'processing'
                }
                uploadState={uploadState}
              />
            )}

            {!isNewUploadMode && uploadState.filename && uploadState.phase === 'ready' && (
              <Paper sx={{ px: 3, py: 2 }}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  SELECTED FILE
                </Typography>
                <Typography variant="subtitle1" fontWeight={600}>
                  {uploadState.filename}
                </Typography>
              </Paper>
            )}

            {uploadState.phase === 'ready' && activeFileId && (
              <FileDataPreview
                data={fileDataQuery.data}
                page={previewPage}
                pageSize={previewPageSize}
                onPageChange={setPreviewPage}
                onPageSizeChange={(size) => {
                  setPreviewPageSize(size)
                  setPreviewPage(1)
                }}
                loading={fileDataQuery.isFetching}
                error={fileDataQuery.error?.message}
              />
            )}

            {showTransformForm && (
              <TransformForm
                columns={uploadState.columns ?? []}
                transformType={transformType}
                naturalLanguagePrompt={naturalLanguagePrompt}
                replacementValue={replacementValue}
                selectedColumns={selectedColumns}
                onTransformTypeChange={setTransformType}
                onPromptChange={setNaturalLanguagePrompt}
                onReplacementChange={setReplacementValue}
                onColumnToggle={(column) => {
                  setSelectedColumns((prev) =>
                    prev.includes(column)
                      ? prev.filter((item) => item !== column)
                      : [...prev, column],
                  )
                }}
                onSubmit={handleSubmit}
                disabled={formDisabled}
                submitting={transformMutation.isPending}
              />
            )}

            {job && (
              <JobProgressPanel
                job={job}
                onCancel={handleCancel}
                cancelling={cancelMutation.isPending}
              />
            )}

            {job?.status === 'SUCCESS' && (
              <ResultsTable
                results={resultsQuery.data}
                page={resultsPage}
                pageSize={resultsPageSize}
                onPageChange={setResultsPage}
                onPageSizeChange={(size) => {
                  setResultsPageSize(size)
                  setResultsPage(1)
                }}
                loading={resultsQuery.isFetching}
                error={resultsQuery.error?.message}
              />
            )}
          </Stack>
        </Container>
      </Box>
    </Box>
  )
}
