import React from 'react';
import './KundliChart.css';

/**
 * KundliChart
 * Renders the SVG chart in either full or compact mode.
 * - compact=true shows only the chart (for embedding as a chat card)
 * - Post-processing normalizes multi-line tspans without moving label anchors
 */
const KundliChart = ({ chartData, onChartReady, compact = false }) => {
  const { svg_content, format, chart_type, ayanamsa, astrology_system } = chartData || {};

  React.useEffect(() => {
    if (svg_content && onChartReady) {
      onChartReady();
    }
  }, [svg_content, onChartReady]);

  // Normalize multi-line <tspan> spacing ONLY (no repositioning) to preserve engine layout
  React.useEffect(() => {
    if (!svg_content) return;
    const timer = setTimeout(() => {
      try {
        const root = document.querySelector('.svg-chart svg');
        if (!root) return;
        Array.from(root.querySelectorAll('text')).forEach((t) => {
          const tspans = Array.from(t.querySelectorAll('tspan'));
          if (tspans.length > 1) {
            const baseX = t.getAttribute('x') || '0';
            tspans.forEach((sp, idx) => {
              sp.setAttribute('x', baseX);
              sp.setAttribute('dy', idx === 0 ? '0' : '1.05em');
            });
          }
          if (!t.getAttribute('text-anchor')) t.setAttribute('text-anchor', 'middle');
          if (!t.getAttribute('dominant-baseline')) t.setAttribute('dominant-baseline', 'middle');
        });
      } catch (_) {}
    }, 0);
    return () => clearTimeout(timer);
  }, [svg_content]);

  const renderSVGChart = () => {
    if (svg_content) {
      return (
        <div className="svg-chart-container">
          <div 
            className="svg-chart"
            dangerouslySetInnerHTML={{ __html: svg_content }}
          />
        </div>
      );
    }
    return (
      <div className="chart-placeholder">
        <div className="chart-loading">
          <div className="spinner"></div>
          <p>Generating your Kundli chart...</p>
        </div>
      </div>
    );
  };

  const renderChartInfo = () => {
    if (!astrology_system) return null;
    
    return (
      <div className="chart-info">
        <h3>🌟 Your Kundli Chart</h3>
        <div className="chart-details">
          <div className="detail-item">
            <span className="label">Astrology System:</span>
            <span className="value">{astrology_system} Astrology</span>
          </div>
          <div className="detail-item">
            <span className="label">Chart Style:</span>
            <span className="value">{chart_type?.replace('-', ' ').toUpperCase()}</span>
          </div>
          <div className="detail-item">
            <span className="label">Ayanamsa:</span>
            <span className="value">{ayanamsa} (KP System)</span>
          </div>
        </div>
      </div>
    );
  };

  if (compact) {
    return (
      <div className="kundli-chart-container compact">
        <div className="chart-wrapper compact">
          {renderSVGChart()}
        </div>
      </div>
    );
  }

  return (
    <div className="kundli-chart-container">
      {renderChartInfo()}
      <div className="chart-wrapper">
        {renderSVGChart()}
      </div>
      <div className="chart-instructions">
        <p>📋 <strong>Your Kundli chart is ready!</strong> You can now ask me any questions about your chart, planetary positions, or astrological predictions.</p>
      </div>
    </div>
  );
};

export default KundliChart;
