import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        // You can also log the error to an error reporting service
        this.setState({ errorInfo });
        console.error("ErrorBoundary caught an error", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            // You can render any custom fallback UI
            return (
                <div style={{ padding: '20px', color: 'red', backgroundColor: '#fff', height: '100vh', overflow: 'auto' }}>
                    <h1>Something went wrong.</h1>
                    <h2>{this.state.error && this.state.error.toString()}</h2>
                    <br />
                    <details style={{ whiteSpace: 'pre-wrap' }}>
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                    </details>
                    <button onClick={() => window.location.reload()} style={{ marginTop: '20px', padding: '10px' }}>
                        Reload Application
                    </button>
                    <button onClick={() => window.history.back()} style={{ marginTop: '20px', padding: '10px', marginLeft: '10px' }}>
                        Go Back
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
