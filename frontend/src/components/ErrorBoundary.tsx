import { Component, type ReactNode } from 'react'

/** Keeps a crash in one tab from blanking the whole app. */
export default class ErrorBoundary extends Component<{ children: ReactNode; label: string; resetKey?: unknown }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  componentDidUpdate(prev: { resetKey?: unknown }) { if (prev.resetKey !== this.props.resetKey && this.state.err) this.setState({ err: null }) }
  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="h-full grid place-items-center p-8">
        <div className="card p-6 max-w-md text-center">
          <div className="font-semibold mb-1">{this.props.label} hit an error</div>
          <p className="text-sm text-muted mb-4 break-words">{this.state.err.message}</p>
          <button className="btn btn-primary mx-auto" onClick={() => this.setState({ err: null })}>Try again</button>
        </div>
      </div>
    )
  }
}
