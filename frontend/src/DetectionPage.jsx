import { useEffect, useState } from 'react'
import { api } from './api.js'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ACCEPTED_TYPES = new Set(['image/jpeg', 'image/png'])
const ACCEPTED_EXTENSIONS = /\.(jpe?g|png)$/i

function formatFileSize(size) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

function ScanIcon({ name }) {
  return (
    <svg aria-hidden="true" fill="none" height="19" viewBox="0 0 24 24" width="19" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7">
      {name === 'upload'
        ? <><path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" /></>
        : name === 'download'
          ? <><path d="M12 4v12m0 0 5-5m-5 5-5-5" /><path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" /></>
          : <><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><path d="M8 12h8m-4-4v8" /></>}
    </svg>
  )
}

export default function DetectionPage() {
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [dimensions, setDimensions] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [dragging, setDragging] = useState(false)

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  function chooseFile(candidate) {
    setError('')
    setResult(null)
    setDimensions(null)
    if (!candidate) return
    if (!ACCEPTED_TYPES.has(candidate.type) || !ACCEPTED_EXTENSIONS.test(candidate.name)) {
      setFile(null)
      setPreviewUrl('')
      setError('Choose a JPG, JPEG, or PNG image.')
      return
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null)
      setPreviewUrl('')
      setError('Image files must be 10 MB or smaller.')
      return
    }
    setPreviewUrl(URL.createObjectURL(candidate))
    setFile(candidate)
  }

  async function submit(event) {
    event.preventDefault()
    if (!file || loading) return
    setError('')
    setLoading(true)
    try {
      const prediction = await api.detect(file)
      setResult(prediction)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Object detection failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="detection-page">
      <div className="page-heading detection-heading">
        <div>
          <p className="page-kicker">AI-POWERED ANALYSIS</p>
          <h1>Object detection<span className="greeting-dot">.</span></h1>
          <p className="page-subtitle">Upload an image to identify and locate objects with YOLO.</p>
        </div>
        <div className="detection-model-pill"><span /> YOLO11N <i>·</i> OBJECT DETECTION</div>
      </div>

      <form className="detection-workspace" onSubmit={submit}>
        <section className="panel detection-upload-panel">
          <div className="detection-panel-heading">
            <div><p className="section-eyebrow">IMAGE INPUT</p><h2>Choose an image</h2></div>
            <span className="upload-format-label">JPG · PNG · MAX 10 MB</span>
          </div>

          {!file ? (
            <label
              className={`upload-dropzone ${dragging ? 'upload-dropzone-active' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault()
                setDragging(false)
                chooseFile(event.dataTransfer.files[0])
              }}
            >
              <input
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                aria-label="Choose an image to analyze"
                onChange={(event) => chooseFile(event.target.files?.[0])}
                type="file"
              />
              <span className="upload-icon"><ScanIcon name="upload" /></span>
              <b>Drop your image here</b>
              <span className="upload-prompt">or <span>browse files</span> from your device</span>
              <small>Supported formats: JPG, JPEG, PNG</small>
            </label>
          ) : (
            <div className="image-preview-card">
              <div className="image-preview-frame">
                <img
                  alt={`Preview of ${file.name}`}
                  onError={() => { setFile(null); setPreviewUrl(''); setError('This file could not be decoded as an image.') }}
                  onLoad={(event) => setDimensions({
                    width: event.currentTarget.naturalWidth,
                    height: event.currentTarget.naturalHeight,
                  })}
                  src={previewUrl}
                />
              </div>
              <div className="image-file-info">
                <span className="file-thumb"><ScanIcon name="image" /></span>
                <span className="file-copy"><b>{file.name}</b><small>{dimensions ? `${dimensions.width} × ${dimensions.height} px · ` : ''}{formatFileSize(file.size)}</small></span>
                <button className="change-image-button" onClick={() => { setFile(null); setPreviewUrl(''); setResult(null) }} type="button">Change</button>
              </div>
            </div>
          )}

          {error && <div className="detection-error" role="alert">{error}</div>}
          <button className="button button-primary detect-submit" disabled={!file || loading} type="submit">
            {loading ? <><span className="button-spinner" /> Analyzing image…</> : <><ScanIcon name="scan" /> Run object detection</>}
          </button>
          <p className="detection-privacy"><span /> Images are analyzed securely and results are saved to your account.</p>
        </section>

        <section className={`panel detection-results-panel ${result ? 'detection-results-ready' : ''}`} aria-live="polite">
          <div className="detection-panel-heading">
            <div><p className="section-eyebrow">INFERENCE OUTPUT</p><h2>Detection results</h2></div>
            {result && <span className="result-run-id">RUN #{result.id}</span>}
          </div>

          {loading ? (
            <div className="inference-loading"><span className="inference-ring" /><b>Analyzing your image</b><span>Running YOLO inference. This may take a moment on first use.</span></div>
          ) : result ? (
            <div className="detection-result-content">
              <div className="annotated-image-frame">
                <img alt="Processed image with object detection boxes" src={result.image_url} />
              </div>
              <div className="result-summary">
                <div><span className="result-total">{result.detections.length}</span><span className="result-total-label">{result.detections.length === 1 ? 'object detected' : 'objects detected'}</span></div>
                <a className="download-image-button" href={result.image_url} download={`visionai-detection-${result.id}.jpg`}><ScanIcon name="download" /> Download</a>
              </div>
              <div className="result-metadata">
                <div><span>IMAGE DIMENSIONS</span><b>{result.width} × {result.height} px</b></div>
                <div><span>ORIGINAL FILE SIZE</span><b>{formatFileSize(result.file_size)}</b></div>
                <div><span>FILE</span><b title={result.original_filename}>{result.original_filename}</b></div>
              </div>
              <div className="detection-list-heading"><span>DETECTED OBJECTS</span><span>CONFIDENCE · BOUNDING BOX</span></div>
              {result.detections.length ? (
                <div className="detection-list">
                  {result.detections.map((detection, index) => (
                    <article className="detection-item" key={`${detection.name}-${index}`}>
                      <span className="detection-index">{String(index + 1).padStart(2, '0')}</span>
                      <span className="detection-object-copy"><b>{detection.name}</b><small>{`x1 ${detection.box.x1} · y1 ${detection.box.y1} · x2 ${detection.box.x2} · y2 ${detection.box.y2}`}</small></span>
                      <span className="detection-confidence">{(detection.confidence * 100).toFixed(1)}%</span>
                    </article>
                  ))}
                </div>
              ) : <div className="no-detections">No objects were detected in this image.</div>}
            </div>
          ) : (
            <div className="results-empty">
              <span className="results-empty-icon"><ScanIcon name="scan" /></span>
              <b>Your results will appear here</b>
              <span>Choose an image and run object detection to see recognized objects and their locations.</span>
            </div>
          )}
        </section>
      </form>
    </div>
  )
}
