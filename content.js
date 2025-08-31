let analysisBox = null;
let buttonContainer = null;
let currentSelectedText = null;
let extensionEnabled = true;

// Text selection utilities
function getSelectedText() {
  const selection = window.getSelection();
  if (selection.rangeCount > 0 && !selection.isCollapsed) {
    return selection.toString().trim();
  }
  return null;
}

function getSelectionBounds() {
  const selection = window.getSelection();
  if (selection.rangeCount > 0) {
    const range = selection.getRangeAt(0);
    return range.getBoundingClientRect();
  }
  return null;
}

function isValidSelection(text) {
  return text && text.length > 3 && text.length < 1000;
}

// Create analysis box element
function createAnalysisBox() {
  if (analysisBox) return analysisBox;
  
  analysisBox = document.createElement('div');
  analysisBox.id = 'ai-analysis-box';
  analysisBox.innerHTML = `
    <div class="analysis-header">
      <span class="analysis-title">Truely Analysis</span>
      <div class="analysis-mode-indicator"></div>
      <button class="analysis-close">&times;</button>
    </div>
    <div class="analysis-content">
      <div class="analysis-result">
        <div class="result-content">Select text or hover over links to get started!</div>
      </div>
    </div>
  `;
  
  document.body.appendChild(analysisBox);
  
  // Add close button functionality
  analysisBox.querySelector('.analysis-close').addEventListener('click', hideAnalysisBox);
  
  return analysisBox;
}

// Position analysis box (fixed to right side)
function positionAnalysisBox() {
  const analysisBox = createAnalysisBox();
  analysisBox.style.position = 'fixed';
  analysisBox.style.right = '20px';
  analysisBox.style.top = '50%';
  analysisBox.style.transform = 'translateY(-50%)';
  analysisBox.style.zIndex = '10000';
}

// Extract unique sources from response data
function extractUniqueSources(data) {
  const uniqueSources = new Map();
  
  // Extract from context chunks (from database query)
  if (data.context && data.context.length > 0) {
    data.context.forEach(contextItem => {
      if (contextItem.source_file && contextItem.source_file !== 'unknown') {
        const cleanFileName = contextItem.source_file.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
        uniqueSources.set(contextItem.source_file, {
          name: cleanFileName,
          url: contextItem.document_url,
          confidence: contextItem.confidence
        });
      }
    });
  }
  
  // Extract from fact-check sources (from LLM response)
  if (data.fact_check && data.fact_check.sources_used) {
    data.fact_check.sources_used.forEach(source => {
      if (source.file_name && source.file_name !== 'unknown') {
        const cleanFileName = source.file_name.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
        uniqueSources.set(source.file_name, {
          name: cleanFileName,
          url: source.document_url,
          confidence: null // LLM sources don't have confidence scores
        });
      }
    });
  }
  
  return Array.from(uniqueSources.values());
}

// Format analysis content with separate sources handling
function formatAnalysisContent(content, sourcesData = null) {
  // Remove any existing source references from the content text
  let cleanContent = content
    .replace(/Based on the information from Source \d+,?/gi, 'Based on the available information,')
    .replace(/According to Source \d+,?/gi, 'According to the documentation,')
    .replace(/Source \d+ indicates/gi, 'The documentation indicates')
    .replace(/from Source \d+/gi, 'from the available sources');
  
  let html = convertMarkdownLinks(cleanContent.trim()).replace(/\n/g, '<br>');
  
  // Add sources section if we have sources data
  if (sourcesData && sourcesData.length > 0) {
    html += '<div class="sources-section">';
    html += '<div class="sources-header">Sources: </div>';
    const sourceLinks = sourcesData.map(source => {
      if (source.url) {
        return `<a href="${source.url}" target="_blank" rel="noopener" class="source-link">${source.name}</a>`;
      } else {
        return source.name;
      }
    });
    html += sourceLinks.join(', ');
    html += '</div>';
  }
  
  return html;
}

// Convert markdown links to HTML links
function convertMarkdownLinks(content) {
  // Convert [text](url) to <a href="url" target="_blank" rel="noopener">text</a>
  return content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="source-link">$1</a>');
}

// Show analysis result (replaces previous result)
function showAnalysisResult(content, sourcesData = null) {
  const analysisBox = createAnalysisBox();
  const contentContainer = analysisBox.querySelector('.analysis-content');
  
  // Format content with proper structure and sources
  const htmlContent = formatAnalysisContent(content, sourcesData);
  
  // Clear previous result and show new one
  contentContainer.innerHTML = `
    <div class="analysis-result">
      <div class="result-content">
        <span class="mode-icon">VERIFIED</span>
        ${htmlContent}
      </div>
    </div>
  `;
}



// Fact check mode analysis - now using real API
async function fetchFactCheckAnalysis(content) {
  try {
    console.log('Making API call to backend');

    const response = await fetch('http://localhost:8877/fact-check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: content,
        n_results: 5,
        use_llm: true
      }),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    const data = await response.json();
    
    // Format the response for display
    let formattedContent = `Fact-checking: "${content}"\n\n`;
    
    if (data.fact_check) {
      const fc = data.fact_check;
      
      // Get classification icon
      let classificationIcon = 'WARNING';
      if (fc.classification === 'SUPPORTED') classificationIcon = 'SUPPORTED';
      else if (fc.classification === 'CONTRADICTED') classificationIcon = 'CONTRADICTED';
      else if (fc.classification === 'INSUFFICIENT') classificationIcon = 'INSUFFICIENT';
      else if (fc.classification === 'MIXED') classificationIcon = 'MIXED';
      
      formattedContent += `${classificationIcon} ${fc.classification}\n\n`;
      
      if (fc.reasoning) {
        formattedContent += `${fc.reasoning}`;
      }
    } else {
      // Fallback if no fact-check response
      formattedContent += `Analysis completed\n\n`;
      if (data.context && data.context.length > 0) {
        formattedContent += `Found ${data.context.length} relevant document(s). Review the context and cross-reference with authoritative sources.`;
      } else {
        formattedContent += `No relevant context found. Verify claims with authoritative sources and fact-checking websites.`;
      }
    }

    return {
      content: formattedContent,
      data: data, // Include raw data for source extraction
      status: 'success'
    };
    
  } catch (error) {
    console.error('Fact-check API error:', error);
    
    // Fallback to basic analysis if API fails
    return {
      content: `Fact-checking: "${content}"\n\nConnection failed\n\nUnable to connect to the fact-checking service. Please ensure the backend is running and try again.`,
      data: null,
      status: 'error'
    };
  }
}


// Show analysis box with analysis
async function showAnalysisResult_async(content) {
  const analysisBox = createAnalysisBox();
  positionAnalysisBox();
  
  // Show loading message
  showAnalysisResult('Analyzing...');
  
  // Show analysis box
  analysisBox.classList.add('visible');
  
  // Update mode indicator
  const modeIndicator = analysisBox.querySelector('.analysis-mode-indicator');
  modeIndicator.textContent = 'Fact Check Mode';
  modeIndicator.className = 'analysis-mode-indicator factcheck';
  
  // Fetch and display analysis
  const analysis = await fetchFactCheckAnalysis(content);
  
  // Extract unique sources from the response
  const uniqueSources = analysis.data ? extractUniqueSources(analysis.data) : [];
  
  // Show analysis result with sources (replaces loading message)
  showAnalysisResult(analysis.content, uniqueSources);
}

// Hide analysis box
function hideAnalysisBox() {
  if (analysisBox) {
    analysisBox.classList.remove('visible');
  }
}

// Clear analysis content
function clearAnalysisContent() {
  if (analysisBox) {
    const contentContainer = analysisBox.querySelector('.analysis-content');
    contentContainer.innerHTML = `
      <div class="analysis-result">
        <div class="result-content">Select text or hover over links to get started!</div>
      </div>
    `;
  }
}


// Create button container with Fact Check button only
function createButtonContainer() {
  if (buttonContainer) return buttonContainer;
  
  buttonContainer = document.createElement('div');
  buttonContainer.id = 'action-buttons';
  buttonContainer.innerHTML = `
    <button class="action-btn factcheck-btn" title="Fact-check this content">
      <span class="btn-icon">CHECK</span>
      <span class="btn-text">Fact Check</span>
    </button>
  `;
  
  document.body.appendChild(buttonContainer);
  
  // Add click event
  const factCheckBtn = buttonContainer.querySelector('.factcheck-btn');
  
  factCheckBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideButtonContainer();
    
    if (currentSelectedText) {
      showAnalysisResult_async(currentSelectedText, 'factcheck');
    }
  });
  
  return buttonContainer;
}

// Position button container near the content
function positionButtonContainer(target, isSelection = false) {
  const container = createButtonContainer();
  let rect;
  
  if (isSelection) {
    rect = getSelectionBounds();
    if (!rect) return;
  } else {
    rect = target.getBoundingClientRect();
  }
  
  let top = rect.bottom + window.scrollY + 10;
  let left = rect.left + window.scrollX;
  
  // Adjust if container would go off screen
  if (left + 200 > window.innerWidth) {
    left = window.innerWidth - 220;
  }
  
  if (top + 50 > window.innerHeight + window.scrollY) {
    top = rect.top + window.scrollY - 60;
  }
  
  container.style.top = `${top}px`;
  container.style.left = `${left}px`;
}

// Show button container
function showButtonContainer(target, isSelection = false) {
  positionButtonContainer(target, isSelection);
  const container = createButtonContainer();
  container.classList.add('visible');
}

// Hide button container
function hideButtonContainer() {
  if (buttonContainer) {
    buttonContainer.classList.remove('visible');
  }
}

// Handle text selection
function handleTextSelection() {
  console.log('Text selection event triggered, extensionEnabled:', extensionEnabled);
  
  // Check if extension is enabled
  if (!extensionEnabled) {
    console.log('Extension is disabled, returning');
    return;
  }
  
  setTimeout(() => {
    const selectedText = getSelectedText();
    console.log('Selected text:', selectedText);
    
    if (selectedText && isValidSelection(selectedText)) {
      console.log('Valid selection, showing button container');
      currentSelectedText = selectedText;
      showButtonContainer(null, true);
    } else {
      console.log('Invalid or no selection, hiding button container');
      currentSelectedText = null;
      hideButtonContainer();
    }
  }, 100);
}



// Initialize extension
function init() {
  // Listen for messages from popup
  chrome.runtime.onMessage.addListener(function(request) {
    if (request.action === 'toggleExtension') {
      extensionEnabled = request.enabled;
      if (!extensionEnabled) {
        hideAnalysisBox();
        hideButtonContainer();
        currentSelectedText = null;
      } else {
        // Re-enable functionality - clear any disabled state
        currentSelectedText = null;
        // If there's currently selected text, handle it
        const selectedText = getSelectedText();
        if (selectedText && isValidSelection(selectedText)) {
          currentSelectedText = selectedText;
          showButtonContainer(null, true);
        }
      }
    }
  });
  
  // Load extension enabled state from storage, then set up event listeners
  if (chrome.storage && (chrome.storage.sync || chrome.storage.local)) {
    const storage = chrome.storage.sync || chrome.storage.local;
    storage.get(['extensionEnabled'], function(data) {
      extensionEnabled = data.extensionEnabled !== false; // Default to true
      
      // Add event listeners for text selection after loading state
      document.addEventListener('mouseup', handleTextSelection);
      document.addEventListener('keyup', handleTextSelection);
      
      console.log('Truely AI Fact Checker extension loaded - enabled:', extensionEnabled);
    });
  } else {
    // Fallback: if storage API is not available, just enable the extension
    extensionEnabled = true;
    document.addEventListener('mouseup', handleTextSelection);
    document.addEventListener('keyup', handleTextSelection);
    console.log('Truely AI Fact Checker extension loaded - storage not available, defaulting to enabled');
  }
  
  // Hide analysis box and buttons when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#ai-analysis-box') && !e.target.closest('#action-buttons')) {
      hideAnalysisBox();
      hideButtonContainer();
      currentSelectedText = null;
    }
  });
  
  // Handle escape key to close analysis box
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideAnalysisBox();
      hideButtonContainer();
      currentSelectedText = null;
    }
  });
}

// Start the extension
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}