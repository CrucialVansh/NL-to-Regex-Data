export const queryKeys = {
  uploads: {
    all: ['uploads'],
  },
  uploadStatus: (id) => ['uploads', id, 'status'],
  uploadData: (id, page, pageSize) => ['uploads', id, 'data', page, pageSize],
  jobStatus: (id) => ['jobs', id, 'status'],
  jobResults: (id, page, pageSize) => ['jobs', id, 'results', page, pageSize],
}
