import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

function formatFileSize(size) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

export default function HistoryPage() {
  const [routeResult] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    const type = params.get('type')
    const id = Number(params.get('id'))
    return ['detection', 'classification'].includes(type) && Number.isInteger(id) && id > 0
      ? { type, id }
      : null
  })
  const [records, setRecords] = useState(null)
  const [error, setError] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [selectedId, setSelectedId] = useState(routeResult?.type === 'detection' ? routeResult.id : null)
  const [selectedRecord, setSelectedRecord] = useState(null)
  const [detailError, setDetailError] = useState('')
  const [loadingRecord, setLoadingRecord] = useState(routeResult?.type === 'detection')
  const detailRequest = useRef(0)
  const [classificationRecords, setClassificationRecords] = useState(null)
  const [classificationError, setClassificationError] = useState('')
  const [selectedClassificationId, setSelectedClassificationId] = useState(routeResult?.type === 'classification' ? routeResult.id : null)
  const [selectedClassification, setSelectedClassification] = useState(null)
  const [classificationDetailError, setClassificationDetailError] = useState('')
  const [loadingClassification, setLoadingClassification] = useState(routeResult?.type === 'classification')
  const classificationDetailRequest = useRef(0)

  useEffect(() => {
    let active = true
    api.detections()
      .then((history) => {
        if (active) setRecords(history)
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : 'Unable to load your history.')
        }
      })

    return () => {
      active = false
    }
  }, [retryCount])

  useEffect(() => {
    let active = true
    api.classifications()
      .then((history) => {
        if (active) setClassificationRecords(history)
      })
      .catch((requestError) => {
        if (active) {
          setClassificationError(requestError instanceof Error ? requestError.message : 'Unable to load classification history.')
        }
      })

    return () => {
      active = false
    }
  }, [retryCount])

  const openRecord = useCallback(async (id) => {
    const requestId = detailRequest.current + 1
    detailRequest.current = requestId
    setSelectedId(id)
    setSelectedRecord(null)
    setDetailError('')
    setLoadingRecord(true)

    try {
      const record = await api.detection(id)
      if (detailRequest.current === requestId) setSelectedRecord(record)
    } catch (requestError) {
      if (detailRequest.current === requestId) {
        setDetailError(requestError instanceof Error ? requestError.message : 'Unable to load this result.')
      }
    } finally {
      if (detailRequest.current === requestId) setLoadingRecord(false)
    }
  }, [])

  const openClassification = useCallback(async (id) => {
    const requestId = classificationDetailRequest.current + 1
    classificationDetailRequest.current = requestId
    setSelectedClassificationId(id)
    setSelectedClassification(null)
    setClassificationDetailError('')
    setLoadingClassification(true)

    try {
      const record = await api.classification(id)
      if (classificationDetailRequest.current === requestId) setSelectedClassification(record)
    } catch (requestError) {
      if (classificationDetailRequest.current === requestId) {
        setClassificationDetailError(requestError instanceof Error ? requestError.message : 'Unable to load this classification.')
      }
    } finally {
      if (classificationDetailRequest.current === requestId) setLoadingClassification(false)
    }
  }, [])

  useEffect(() => {
    if (routeResult?.type === 'detection') {
      const requestId = detailRequest.current + 1
      detailRequest.current = requestId
      void api.detection(routeResult.id)
        .then((record) => {
          if (detailRequest.current === requestId) setSelectedRecord(record)
        })
        .catch((requestError) => {
          if (detailRequest.current === requestId) {
            setDetailError(requestError instanceof Error ? requestError.message : 'Unable to load this result.')
          }
        })
        .finally(() => {
          if (detailRequest.current === requestId) setLoadingRecord(false)
        })
    } else if (routeResult?.type === 'classification') {
      const requestId = classificationDetailRequest.current + 1
      classificationDetailRequest.current = requestId
      void api.classification(routeResult.id)
        .then((record) => {
          if (classificationDetailRequest.current === requestId) setSelectedClassification(record)
        })
        .catch((requestError) => {
          if (classificationDetailRequest.current === requestId) {
            setClassificationDetailError(requestError instanceof Error ? requestError.message : 'Unable to load this classification.')
          }
        })
        .finally(() => {
          if (classificationDetailRequest.current === requestId) setLoadingClassification(false)
        })
    }
  }, [routeResult])

  return (
    <div className="history-page">
      <div className="page-heading">
        <div>
          <p className="page-kicker">YOUR RECORDS</p>
          <h1>Analysis history<span className="greeting-dot">.</span></h1>
          <p className="page-subtitle">Review your saved image analyses and results.</p>
        </div>
      </div>

      {records === null && !error ? (
        <section className="panel history-state" aria-live="polite">
          <span className="loading-ring" />
          <b>Loading your history</b>
          <span>Your saved analyses will appear here.</span>
        </section>
      ) : error ? (
        <section className="panel history-state" role="alert">
          <b>History could not be loaded</b>
          <span>{error}</span>
          <button className="button button-primary history-retry" onClick={() => {
            setRecords(null)
            setError('')
            setRetryCount((count) => count + 1)
          }} type="button">
            Try again
          </button>
        </section>
      ) : records.length === 0 ? (
        <section className="panel history-state">
          <span className="history-empty-icon" aria-hidden="true">⌁</span>
          <b>No analyses yet</b>
          <span>Completed image analyses will appear here.</span>
        </section>
      ) : (
        <>
          <section aria-label="Saved image analyses" className="history-list">
            {records.map((record) => (
              <article className={`panel history-record ${selectedId === record.id ? 'history-record-selected' : ''}`} key={record.id}>
                <img
                  alt={`Processed image for ${record.original_filename}`}
                  className="history-thumbnail"
                  loading="lazy"
                  src={record.image_url}
                />
                <div className="history-record-copy">
                  <b className="history-filename" title={record.original_filename}>{record.original_filename}</b>
                  <time dateTime={record.created_at}>{formatDate(record.created_at)}</time>
                  <span>{record.detections.length} {record.detections.length === 1 ? 'object detected' : 'objects detected'}</span>
                </div>
                <div className="history-record-status">
                  <span className="history-status-complete"><i /> Complete</span>
                  <button
                    aria-label={`Open results for ${record.original_filename}`}
                    className="history-open-button"
                    disabled={loadingRecord && selectedId === record.id}
                    onClick={() => openRecord(record.id)}
                    type="button"
                  >
                    {loadingRecord && selectedId === record.id ? 'Opening…' : 'View results'}
                  </button>
                </div>
              </article>
            ))}
          </section>

          {selectedId !== null && (
            <section aria-live="polite" className="panel history-detail">
              <div className="detection-panel-heading">
                <div>
                  <p className="section-eyebrow">SAVED ANALYSIS</p>
                  <h2>{selectedRecord?.original_filename ?? 'Analysis results'}</h2>
                </div>
                <button className="history-close-button" onClick={() => {
                  detailRequest.current += 1
                  setSelectedId(null)
                  setSelectedRecord(null)
                  setDetailError('')
                  setLoadingRecord(false)
                }} type="button">
                  Close
                </button>
              </div>

              {loadingRecord ? (
                <div className="history-detail-state" aria-live="polite">
                  <span className="loading-ring" />
                  <span>Loading saved results…</span>
                </div>
              ) : detailError ? (
                <div className="history-detail-state" role="alert">
                  <span>{detailError}</span>
                  <button className="history-open-button" onClick={() => openRecord(selectedId)} type="button">Try again</button>
                </div>
              ) : selectedRecord ? (
                <div className="detection-result-content">
                  <div className="annotated-image-frame">
                    <img alt={`Processed image for ${selectedRecord.original_filename}`} src={selectedRecord.image_url} />
                  </div>
                  <div className="result-summary">
                    <div>
                      <span className="result-total">{selectedRecord.detections.length}</span>
                      <span className="result-total-label">
                        {selectedRecord.detections.length === 1 ? 'object detected' : 'objects detected'}
                      </span>
                    </div>
                    <span className="history-status-complete"><i /> Complete</span>
                  </div>
                  <div className="result-metadata">
                    <div><span>UPLOAD DATE</span><b>{formatDate(selectedRecord.created_at)}</b></div>
                    <div><span>FILE SIZE</span><b>{formatFileSize(selectedRecord.file_size)}</b></div>
                    <div><span>IMAGE DIMENSIONS</span><b>{selectedRecord.width} × {selectedRecord.height} px</b></div>
                    <div><span>ORIGINAL FILENAME</span><b title={selectedRecord.original_filename}>{selectedRecord.original_filename}</b></div>
                  </div>
                  <div className="detection-list-heading">
                    <span>DETECTED OBJECTS</span>
                    <span>CONFIDENCE · BOUNDING BOX</span>
                  </div>
                  {selectedRecord.detections.length ? (
                    <div className="detection-list">
                      {selectedRecord.detections.map((detection, index) => (
                        <article className="detection-item" key={`${detection.name}-${index}`}>
                          <span className="detection-index">{String(index + 1).padStart(2, '0')}</span>
                          <span className="detection-object-copy">
                            <b>{detection.name}</b>
                            <small>{`x1 ${detection.box.x1} · y1 ${detection.box.y1} · x2 ${detection.box.x2} · y2 ${detection.box.y2}`}</small>
                          </span>
                          <span className="detection-confidence">{(detection.confidence * 100).toFixed(1)}%</span>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="no-detections">No objects were detected in this image.</div>
                  )}
                  <p className="history-image-note">The original upload is not retained; this is the processed image saved with the analysis.</p>
                </div>
              ) : null}
            </section>
          )}
        </>
      )}

      <section aria-label="Saved image classifications" className="classification-history">
        <div className="page-heading">
          <div>
            <p className="page-kicker">SAVED CLASSIFICATIONS</p>
            <h2>Image classification history</h2>
            <p className="page-subtitle">Review your saved category predictions.</p>
          </div>
        </div>

        {classificationRecords === null && !classificationError ? (
          <section className="panel history-state" aria-live="polite">
            <span className="loading-ring" />
            <b>Loading classification history</b>
            <span>Your saved classifications will appear here.</span>
          </section>
        ) : classificationError ? (
          <section className="panel history-state" role="alert">
            <b>Classification history could not be loaded</b>
            <span>{classificationError}</span>
            <button className="button button-primary history-retry" onClick={() => {
              setClassificationRecords(null)
              setClassificationError('')
              setRetryCount((count) => count + 1)
            }} type="button">
              Try again
            </button>
          </section>
        ) : classificationRecords.length === 0 ? (
          <section className="panel history-state">
            <b>No classifications yet</b>
            <span>Completed image classifications will appear here.</span>
          </section>
        ) : (
          <>
            <div className="history-list">
              {classificationRecords.map((record) => (
                <article className={`panel history-record ${selectedClassificationId === record.id ? 'history-record-selected' : ''}`} key={record.id}>
                  <img
                    alt={`Classified image for ${record.original_filename}`}
                    className="history-thumbnail"
                    loading="lazy"
                    src={record.image_url}
                  />
                  <div className="history-record-copy">
                    <b className="history-filename" title={record.original_filename}>{record.original_filename}</b>
                    <time dateTime={record.created_at}>{formatDate(record.created_at)}</time>
                    <span>{record.predictions[0]?.label ?? 'No prediction'} · {record.predictions[0] ? `${(record.predictions[0].confidence * 100).toFixed(1)}%` : '—'}</span>
                  </div>
                  <div className="history-record-status">
                    <span className="history-status-complete"><i /> Complete</span>
                    <button
                      aria-label={`Open classification results for ${record.original_filename}`}
                      className="history-open-button"
                      disabled={loadingClassification && selectedClassificationId === record.id}
                      onClick={() => openClassification(record.id)}
                      type="button"
                    >
                      {loadingClassification && selectedClassificationId === record.id ? 'Opening…' : 'View results'}
                    </button>
                  </div>
                </article>
              ))}
            </div>

            {selectedClassificationId !== null && (
              <section aria-live="polite" className="panel history-detail">
                <div className="detection-panel-heading">
                  <div>
                    <p className="section-eyebrow">SAVED CLASSIFICATION</p>
                    <h2>{selectedClassification?.original_filename ?? 'Classification results'}</h2>
                  </div>
                  <button className="history-close-button" onClick={() => {
                    classificationDetailRequest.current += 1
                    setSelectedClassificationId(null)
                    setSelectedClassification(null)
                    setClassificationDetailError('')
                    setLoadingClassification(false)
                  }} type="button">
                    Close
                  </button>
                </div>

                {loadingClassification ? (
                  <div className="history-detail-state" aria-live="polite">
                    <span className="loading-ring" />
                    <span>Loading saved predictions…</span>
                  </div>
                ) : classificationDetailError ? (
                  <div className="history-detail-state" role="alert">
                    <span>{classificationDetailError}</span>
                    <button className="history-open-button" onClick={() => openClassification(selectedClassificationId)} type="button">Try again</button>
                  </div>
                ) : selectedClassification ? (
                  <div className="detection-result-content">
                    <div className="annotated-image-frame">
                      <img alt={`Classified image for ${selectedClassification.original_filename}`} src={selectedClassification.image_url} />
                    </div>
                    <div className="result-summary">
                      <div>
                        <span className="result-total">{selectedClassification.predictions.length}</span>
                        <span className="result-total-label">ranked predictions</span>
                      </div>
                      <span className="history-status-complete"><i /> Complete</span>
                    </div>
                    <div className="result-metadata">
                      <div><span>UPLOAD DATE</span><b>{formatDate(selectedClassification.created_at)}</b></div>
                      <div><span>FILE SIZE</span><b>{formatFileSize(selectedClassification.file_size)}</b></div>
                      <div><span>IMAGE DIMENSIONS</span><b>{selectedClassification.width} × {selectedClassification.height} px</b></div>
                      <div><span>MODEL</span><b>{selectedClassification.model}</b></div>
                      <div><span>ORIGINAL FILENAME</span><b title={selectedClassification.original_filename}>{selectedClassification.original_filename}</b></div>
                    </div>
                    <div className="detection-list-heading">
                      <span>RANKED LABELS</span>
                      <span>MODEL CONFIDENCE</span>
                    </div>
                    <div className="detection-list">
                      {selectedClassification.predictions.map((prediction, index) => (
                        <article className="detection-item" key={`${prediction.label}-${index}`}>
                          <span className="detection-index">{String(index + 1).padStart(2, '0')}</span>
                          <span className="detection-object-copy"><b>{prediction.label}</b></span>
                          <span className="detection-confidence">{(prediction.confidence * 100).toFixed(1)}%</span>
                        </article>
                      ))}
                    </div>
                    <p className="history-image-note">The original upload is not retained; this is a compressed preview saved with the classification. Predictions are model estimates, not guarantees.</p>
                  </div>
                ) : null}
              </section>
            )}
          </>
        )}
      </section>
    </div>
  )
}
