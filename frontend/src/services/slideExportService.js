import html2pdf from 'html2pdf.js';
import PptxGenJS from 'pptxgenjs';

/**
 * Export the full slide deck to PDF by capturing each slide as rendered HTML.
 * Uses html2pdf.js (which bundles jspdf + html2canvas internally).
 */
export async function exportFullDeckToPDF(slideContainerRef, slideDeck, propertyName, setCurrentSlide) {
  const slides = slideDeck?.slides || [];
  if (!slides.length || !slideContainerRef) return;

  // Navigate to first slide and wait for render
  setCurrentSlide(1);
  await sleep(400);

  const canvas = slideContainerRef.querySelector('.slide-container');
  if (!canvas) return;

  const fileName = `${propertyName.replace(/\s+/g, '_')}_Diagnosis.pdf`;

  // Generate the first page
  const worker = html2pdf()
    .set({
      margin: 0,
      filename: fileName,
      image: { type: 'jpeg', quality: 0.92 },
      html2canvas: { scale: 2, useCORS: true, logging: false },
      jsPDF: { unit: 'in', format: 'letter', orientation: 'landscape' },
    })
    .from(canvas);

  // Get the internal jsPDF instance after rendering the first page
  const pdf = await worker.toPdf().get('pdf');

  // Capture remaining slides
  for (let i = 1; i < slides.length; i++) {
    setCurrentSlide(i + 1);
    await sleep(400);

    pdf.addPage();

    // Use html2pdf to render this slide to the existing PDF
    await html2pdf()
      .set({
        margin: 0,
        image: { type: 'jpeg', quality: 0.92 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'in', format: 'letter', orientation: 'landscape' },
      })
      .from(canvas)
      .toCanvas()
      .then((canvasEl) => {
        const imgData = canvasEl.toDataURL('image/jpeg', 0.92);
        const pageW = 11;
        const pageH = 8.5;
        const imgW = canvasEl.width;
        const imgH = canvasEl.height;
        const ratio = Math.min(pageW / imgW, pageH / imgH);
        const w = imgW * ratio;
        const h = imgH * ratio;
        const x = (pageW - w) / 2;
        const y = (pageH - h) / 2;
        pdf.addImage(imgData, 'JPEG', x, y, w, h);
      });
  }

  pdf.save(fileName);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// Color constants for PPTX
const COLORS = {
  stone900: '1c1917',
  stone700: '44403c',
  stone500: '78716c',
  stone300: 'd6d3d1',
  stone100: 'f5f5f4',
  white: 'FFFFFF',
  positive: '16a34a',
  critical: 'dc2626',
  caution: 'f59e0b',
};

/**
 * Export the slide deck to PowerPoint (.pptx).
 * Generates real editable slides with text content from the slide data.
 */
export function exportToPPTX(slideDeck, propertyName) {
  const slides = slideDeck?.slides || [];
  if (!slides.length) return;

  const pptx = new PptxGenJS();
  pptx.author = 'RoboRev';
  pptx.company = 'RoboRev Revenue Management';
  pptx.subject = `Pricing Diagnosis — ${propertyName}`;
  pptx.title = `${propertyName} — Revenue Management Diagnosis`;
  pptx.layout = 'LAYOUT_WIDE';

  for (const slide of slides) {
    const pptSlide = pptx.addSlide();

    if (slide.slide_type === 'TITLE' || slide.slide_type === 'PORTFOLIO_TITLE') {
      renderTitleSlide(pptSlide, slide, propertyName);
    } else if (slide.slide_type === 'SUMMARY' || slide.slide_type === 'PORTFOLIO_SUMMARY') {
      renderDarkSlide(pptSlide, slide);
    } else {
      renderContentSlide(pptSlide, slide);
    }
  }

  pptx.writeFile({ fileName: `${propertyName.replace(/\s+/g, '_')}_Diagnosis.pptx` });
}

function renderTitleSlide(pptSlide, slide, propertyName) {
  pptSlide.background = { color: COLORS.stone900 };

  pptSlide.addText('ROBOREV', {
    x: 0.8, y: 0.6, w: 11, h: 0.5,
    fontSize: 14, fontFace: 'Arial',
    color: COLORS.stone500, bold: true,
    charSpacing: 6,
  });

  const title = slide.title || `${propertyName} — Pricing Diagnosis`;
  pptSlide.addText(title, {
    x: 0.8, y: 2.0, w: 11, h: 1.2,
    fontSize: 36, fontFace: 'Arial',
    color: COLORS.white, bold: true,
  });

  const subtitle = extractFirstNarrativeLine(slide.narrative);
  if (subtitle) {
    pptSlide.addText(subtitle, {
      x: 0.8, y: 3.4, w: 11, h: 0.6,
      fontSize: 16, fontFace: 'Arial',
      color: COLORS.stone500,
    });
  }

  pptSlide.addText('AI-Powered Revenue Management', {
    x: 0.8, y: 6.2, w: 11, h: 0.5,
    fontSize: 12, fontFace: 'Arial',
    color: COLORS.stone700,
  });
}

function renderDarkSlide(pptSlide, slide) {
  pptSlide.background = { color: COLORS.stone900 };

  pptSlide.addText(slide.title || 'Summary & Next Steps', {
    x: 0.8, y: 0.4, w: 11, h: 0.7,
    fontSize: 24, fontFace: 'Arial',
    color: COLORS.white, bold: true,
  });

  const narrativeText = extractNarrativeText(slide.narrative);
  if (narrativeText) {
    pptSlide.addText(narrativeText, {
      x: 0.8, y: 1.4, w: 11.5, h: 5.0,
      fontSize: 13, fontFace: 'Arial',
      color: COLORS.stone300,
      valign: 'top',
      lineSpacingMultiple: 1.4,
    });
  }
}

function renderContentSlide(pptSlide, slide) {
  pptSlide.background = { color: COLORS.white };

  // Header
  pptSlide.addText(slide.title || '', {
    x: 0.6, y: 0.2, w: 10, h: 0.6,
    fontSize: 20, fontFace: 'Arial',
    color: COLORS.stone900, bold: true,
  });

  // Divider line using a thin rectangle
  pptSlide.addShape('rect', {
    x: 0.6, y: 0.85, w: 12.1, h: 0.01,
    fill: { color: COLORS.stone300 },
  });

  // Narrative content
  const narrativeText = extractNarrativeText(slide.narrative);
  if (narrativeText) {
    pptSlide.addText(narrativeText, {
      x: 0.6, y: 1.1, w: 12, h: 5.5,
      fontSize: 12, fontFace: 'Arial',
      color: COLORS.stone700,
      valign: 'top',
      lineSpacingMultiple: 1.35,
    });
  }

  // KPI data badges from viz_data
  const vizData = slide.viz_data;
  if (vizData && typeof vizData === 'object') {
    const kpis = extractKPIs(vizData);
    if (kpis.length > 0) {
      const kpiText = kpis.map((k) => `${k.label}: ${k.value}`).join('    |    ');
      pptSlide.addText(kpiText, {
        x: 0.6, y: 6.5, w: 12, h: 0.5,
        fontSize: 10, fontFace: 'Arial',
        color: COLORS.stone500, bold: true,
      });
    }
  }
}

function extractNarrativeText(narrative) {
  if (!narrative) return '';
  if (typeof narrative === 'string') return narrative;
  if (typeof narrative === 'object') {
    return Object.values(narrative)
      .filter((v) => typeof v === 'string')
      .join('\n\n');
  }
  return '';
}

function extractFirstNarrativeLine(narrative) {
  const text = extractNarrativeText(narrative);
  if (!text) return '';
  const first = text.split('\n')[0];
  return first.length > 120 ? first.slice(0, 117) + '...' : first;
}

function extractKPIs(vizData) {
  const kpis = [];
  for (const [key, val] of Object.entries(vizData)) {
    if (typeof val === 'number') {
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      const formatted = Number.isInteger(val) ? val.toLocaleString() : val.toFixed(1);
      kpis.push({ label, value: formatted });
    }
    if (kpis.length >= 6) break;
  }
  return kpis;
}
