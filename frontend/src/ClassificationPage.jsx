import { useEffect, useState } from 'react'
import { api } from './api.js'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ACCEPTED_TYPES = new Set(['image/jpeg', 'image/png'])
const ACCEPTED_EXTENSIONS = /\.(jpe?g|png)$/i

function formatFileSize(size) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

function UploadIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="19" viewBox="0 0 24 24" width="19" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7">
      <path d="M12 16V4m0 0L7 9m5-5 5 5" />
      <path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" />
    </svg>
  )
}

export default function ClassificationPage() {
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
      setResult(await api.classify(file))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Image classification failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="detection-page">
      <div className="page-heading detection-heading">
        <div>
          <p className="page-kicker">AI-POWERED ANALYSIS</p>
          <h1>Image classification<span className="greeting-dot">.</span></h1>
          <p className="page-subtitle">Upload an everyday image to rank its most likely ImageNet categories.</p>
        </div>
        <div className="detection-model-pill"><span /> EFFICIENTNET-B0 <i>·</i> IMAGENET-1K</div>
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
                aria-label="Choose an image to classify"
                onChange={(event) => chooseFile(event.target.files?.[0])}
                type="file"
              />
              <span className="upload-icon"><UploadIcon /></span>
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
                <span className="file-thumb"><UploadIcon /></span>
                <span className="file-copy"><b>{file.name}</b><small>{dimensions ? `${dimensions.width} × ${dimensions.height} px · ` : ''}{formatFileSize(file.size)}</small></span>
                <button className="change-image-button" onClick={() => { setFile(null); setPreviewUrl(''); setResult(null) }} type="button">Change</button>
              </div>
            </div>
          )}

          {error && <div className="detection-error" role="alert">{error}</div>}
          <button className="button button-primary detect-submit" disabled={!file || loading} type="submit">
            {loading ? <><span className="button-spinner" /> Classifying image…</> : <><UploadIcon /> Classify image</>}
          </button>
          <p className="detection-privacy"><span /> Images are analyzed securely; a compressed preview and results are saved to your account.</p>
        </section>

        <section className={`panel detection-results-panel ${result ? 'detection-results-ready' : ''}`} aria-live="polite">
          <div className="detection-panel-heading">
            <div><p className="section-eyebrow">CLASSIFICATION OUTPUT</p><h2>Top 3 predictions</h2></div>
            {result && <span className="result-run-id">RUN #{result.id}</span>}
          </div>

          {loading ? (
            <div className="inference-loading"><span className="inference-ring" /><b>Classifying your image</b><span>Running EfficientNet-B0 inference. The first run may take longer while weights load.</span></div>
          ) : result ? (
            <div className="detection-result-content">
              <div className="annotated-image-frame">
                <img alt={`Classified image for ${result.original_filename}`} src={result.image_url} />
              </div>
              <div className="result-summary">
                <div><span className="result-total">{result.predictions.length}</span><span className="result-total-label">ranked predictions</span></div>
              </div>
              <div className="result-metadata">
                <div><span>IMAGE DIMENSIONS</span><b>{result.width} × {result.height} px</b></div>
                <div><span>ORIGINAL FILE SIZE</span><b>{formatFileSize(result.file_size)}</b></div>
                <div><span>FILE</span><b title={result.original_filename}>{result.original_filename}</b></div>
                <div><span>MODEL</span><b>{result.model}</b></div>
              </div>
              <div className="detection-list-heading"><span>RANKED LABELS</span><span>MODEL CONFIDENCE</span></div>
              <div className="detection-list">
                {result.predictions.map((prediction, index) => (
                  <article className="detection-item" key={`${prediction.label}-${index}`}>
                    <span className="detection-index">{String(index + 1).padStart(2, '0')}</span>
                    <span className="detection-object-copy"><b>{prediction.label}</b></span>
                    <span className="detection-confidence">{(prediction.confidence * 100).toFixed(1)}%</span>
                  </article>
                ))}
              </div>
              <p className="history-image-note">Predictions are model estimates, not guarantees or clinically validated results.</p>
            </div>
          ) : (
            <div className="results-empty">
              <span className="results-empty-icon"><UploadIcon /></span>
              <b>Your predictions will appear here</b>
              <span>Choose an image to see the three most likely categories from the ImageNet-1K label set.</span>
            </div>
          )}
        </section>
      </form>
    </div>
  )
}
