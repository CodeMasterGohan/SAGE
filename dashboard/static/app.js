/**
 * SAGE-Docs Dashboard - Frontend Application
 * ===========================================
 * Handles API communication and UI interactions
 * Based on DRUID dashboard with upload functionality added
 */

// State
let currentLibrary = null;
let libraries = [];
let searchTimeout = null;
let currentTab = 'search';

// DOM Elements
const searchInput = document.getElementById('searchInput');
const libraryFilter = document.getElementById('libraryFilter');
const libraryList = document.getElementById('libraryList');
const resultsGrid = document.getElementById('resultsGrid');
const resultsHeader = document.getElementById('resultsHeader');
const resultCount = document.getElementById('resultCount');
const emptyState = document.getElementById('emptyState');
const loadingState = document.getElementById('loadingState');
const connectionStatus = document.getElementById('connectionStatus');
const connectionBadge = document.getElementById('connectionBadge');
const connectionText = document.getElementById('connectionText');
const connectionDot = document.getElementById('connectionDot');
const connectionPing = document.getElementById('connectionPing');
const docCount = document.getElementById('docCount');
const activeFilterSection = document.getElementById('activeFilterSection');
const activeFilterName = document.getElementById('activeFilterName');
const breadcrumbCurrent = document.getElementById('breadcrumbCurrent');
const fusionMethod = document.getElementById('fusionMethod');
const searchSuggestions = document.getElementById('searchSuggestions');
const suggestionList = document.getElementById('suggestionList');

// Upload elements
const searchView = document.getElementById('searchView');
const uploadView = document.getElementById('uploadView');
const tabSearch = document.getElementById('tabSearch');
const tabUpload = document.getElementById('tabUpload');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadLibrary = document.getElementById('uploadLibrary');
const uploadVersion = document.getElementById('uploadVersion');
const uploadProgress = document.getElementById('uploadProgress');
const uploadFileName = document.getElementById('uploadFileName');
const uploadPercent = document.getElementById('uploadPercent');
const uploadProgressBar = document.getElementById('uploadProgressBar');
const uploadResult = document.getElementById('uploadResult');
const uploadResultTitle = document.getElementById('uploadResultTitle');
const uploadResultMessage = document.getElementById('uploadResultMessage');
const libraryManager = document.getElementById('libraryManager');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkConnection();
    loadLibraries();

    // Search on Enter
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Live search with debounce
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const query = searchInput.value.trim();

        if (query.length > 1) {
            searchTimeout = setTimeout(() => {
                showSuggestions(query);
            }, 300);
        } else {
            hideSuggestions();
        }
    });

    // Library filter
    libraryFilter.addEventListener('input', filterLibraries);

    // File upload handlers
    setupUploadHandlers();
});

// Tab switching
function switchTab(tab) {
    currentTab = tab;

    if (tab === 'search') {
        searchView.classList.remove('hidden');
        uploadView.classList.add('hidden');
        tabSearch.classList.add('active');
        tabSearch.classList.remove('text-gray-400');
        tabUpload.classList.remove('active');
        tabUpload.classList.add('text-gray-400');
        breadcrumbCurrent.textContent = currentLibrary || 'Search';
    } else {
        searchView.classList.add('hidden');
        uploadView.classList.remove('hidden');
        tabUpload.classList.add('active');
        tabUpload.classList.remove('text-gray-400');
        tabSearch.classList.remove('active');
        tabSearch.classList.add('text-gray-400');
        breadcrumbCurrent.textContent = 'Upload';
        renderLibraryManager();
    }
}

// Upload handlers
function setupUploadHandlers() {
    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files);
        }
    });
}

async function handleFileUpload(files) {
    const library = uploadLibrary.value.trim();
    const version = uploadVersion.value.trim() || 'latest';

    if (!library) {
        alert('Please enter a library name');
        return;
    }

    // Get status elements
    const uploadStatus = document.getElementById('uploadStatus');

    // Show progress
    uploadProgress.classList.remove('hidden');
    uploadResult.classList.add('hidden');

    let totalFiles = files.length;
    let processed = 0;
    let totalChunks = 0;
    let hasErrors = false;
    let allTruncationWarnings = [];

    for (const file of files) {
        const isPDF = file.name.toLowerCase().endsWith('.pdf');

        // Update status
        uploadFileName.textContent = file.name;
        uploadStatus.textContent = isPDF
            ? 'Starting PDF processing (this may take a while)...'
            : 'Uploading...';

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('library', library);
            formData.append('version', version);

            if (isPDF) {
                // Use async endpoint for PDFs
                uploadStatus.textContent = 'Sending to server...';

                const asyncResponse = await fetch('/api/upload/async', {
                    method: 'POST',
                    body: formData
                });
                const asyncResult = await asyncResponse.json();

                if (asyncResponse.ok) {
                    // Poll for status
                    const taskId = asyncResult.task_id;
                    let status = 'pending';
                    uploadStatus.textContent = 'Converting PDF layout...';

                    while (status === 'pending' || status === 'processing') {
                        await new Promise(resolve => setTimeout(resolve, 2000));

                        const statusResponse = await fetch(`/api/upload/status/${taskId}`);
                        const statusData = await statusResponse.json();
                        status = statusData.status;

                        if (statusData.progress) {
                            uploadStatus.textContent = statusData.progress;
                        }

                        if (status === 'completed' && statusData.result) {
                            totalChunks += statusData.result.chunks_indexed;
                            uploadStatus.textContent = 'Indexing complete!';
                            
                            // Collect truncation warnings
                            if (statusData.result.truncation_warnings && statusData.result.truncation_warnings.length > 0) {
                                allTruncationWarnings.push(...statusData.result.truncation_warnings);
                            }
                        } else if (status === 'failed') {
                            console.error('Upload failed:', statusData.error);
                            uploadStatus.textContent = `Error: ${statusData.error}`;
                            hasErrors = true;
                        }
                    }
                } else {
                    console.error('Async upload failed:', asyncResult);
                    uploadStatus.textContent = 'Upload failed. Check console.';
                    hasErrors = true;
                }
            } else {
                // Use regular sync endpoint for non-PDFs
                uploadStatus.textContent = 'Uploading and processing...';

                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok) {
                    totalChunks += result.chunks_indexed;
                    uploadStatus.textContent = 'Done!';
                    
                    // Collect truncation warnings
                    if (result.truncation_warnings && result.truncation_warnings.length > 0) {
                        allTruncationWarnings.push(...result.truncation_warnings);
                    }
                } else {
                    console.error('Upload failed:', result);
                    uploadStatus.textContent = `Error: ${result.detail || 'Upload failed'}`;
                    hasErrors = true;
                }
            }
        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = `Error: ${error.message}`;
            hasErrors = true;
        }

        processed++;
    }

    // Show result
    uploadProgress.classList.add('hidden');
    uploadResult.classList.remove('hidden');

    if (hasErrors || totalChunks === 0) {
        uploadResultTitle.textContent = totalChunks > 0 ? 'Upload completed with issues' : 'Upload failed';
        uploadResultMessage.innerHTML = totalChunks > 0
            ? `Indexed ${totalChunks} chunks but some files had errors. Check console.`
            : 'No content was indexed. Check console for errors.';
        // Change to error styling
        uploadResult.querySelector('div').className = 'p-4 rounded-lg bg-red-900/20 border border-red-800';
        uploadResult.querySelector('i').className = 'fa-solid fa-exclamation-circle text-red-400 text-xl';
        uploadResultTitle.className = 'text-red-400 font-medium';
        uploadResultMessage.className = 'text-red-300/70 text-sm';
    } else {
        uploadResultTitle.textContent = 'Upload successful!';
        let message = `Indexed ${totalChunks} chunks from ${processed} file(s) into "${library}" v${version}`;
        
        // Add truncation warnings if present
        if (allTruncationWarnings.length > 0) {
            message += renderTruncationWarnings(allTruncationWarnings);
        }
        
        uploadResultMessage.innerHTML = message;
        // Reset to success styling (with warning color if truncations exist)
        if (allTruncationWarnings.length > 0) {
            uploadResult.querySelector('div').className = 'p-4 rounded-lg bg-yellow-900/20 border border-yellow-800';
            uploadResult.querySelector('i').className = 'fa-solid fa-exclamation-triangle text-yellow-400 text-xl';
            uploadResultTitle.className = 'text-yellow-400 font-medium';
            uploadResultMessage.className = 'text-yellow-300/70 text-sm';
        } else {
            uploadResult.querySelector('div').className = 'p-4 rounded-lg bg-green-900/20 border border-green-800';
            uploadResult.querySelector('i').className = 'fa-solid fa-check-circle text-green-400 text-xl';
            uploadResultTitle.className = 'text-green-400 font-medium';
            uploadResultMessage.className = 'text-green-300/70 text-sm';
        }
    }

    // Refresh libraries
    loadLibraries();
    renderLibraryManager();

    // Clear file input
    fileInput.value = '';
}

function renderLibraryManager() {
    if (libraries.length === 0) {
        libraryManager.innerHTML = '<p class="text-gray-500 text-sm">No libraries indexed yet. Upload some documentation!</p>';
        return;
    }

    libraryManager.innerHTML = libraries.map(lib => {
        const safeLibrary = escapeHtml(lib.library);
        const safeLibraryAttr = safeLibrary.replace(/'/g, "\\'");
        return `
        <div class="flex items-center justify-between p-3 bg-[#0d1117] rounded-lg border border-gray-800">
            <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
                    <i class="fa-solid fa-book text-cyan-400 text-sm"></i>
                </div>
                <div>
                    <span class="text-white font-medium">${safeLibrary}</span>
                    <div class="flex gap-1 mt-1">
                        ${lib.versions.map(v => `<span class="text-[10px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-400">${escapeHtml(v)}</span>`).join('')}
                    </div>
                </div>
            </div>
            <button 
                onclick="deleteLibrary('${safeLibraryAttr}')"
                class="delete-btn p-2 rounded-lg text-gray-500 hover:text-red-400"
                title="Delete library"
            >
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    }).join('');
}

async function deleteLibrary(library) {
    if (!confirm(`Delete library "${library}" and all its documents?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/library/${encodeURIComponent(library)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadLibraries();
            renderLibraryManager();
        } else {
            alert('Failed to delete library');
        }
    } catch (error) {
        console.error('Delete failed:', error);
        alert('Failed to delete library');
    }
}

// Check connection status
async function checkConnection() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.connected) {
            setConnectionStatus(true, data.document_count);
        } else {
            setConnectionStatus(false);
        }
    } catch (error) {
        console.error('Connection check failed:', error);
        setConnectionStatus(false);
    }
}

function setConnectionStatus(connected, docs = null) {
    if (connected) {
        connectionStatus.textContent = 'Connected';
        connectionStatus.className = 'text-[10px] text-green-400';
        connectionText.textContent = 'Connected';
        connectionText.className = 'text-[10px] font-bold tracking-wider text-green-400 uppercase';
        connectionBadge.className = 'flex items-center gap-2 px-3 py-1 rounded-full border border-green-500/30 bg-green-950/20';
        connectionDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-green-500';
        connectionPing.className = 'animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75';

        if (docs !== null) {
            docCount.textContent = `${docs.toLocaleString()} docs`;
        }
    } else {
        connectionStatus.textContent = 'Disconnected';
        connectionStatus.className = 'text-[10px] text-red-400';
        connectionText.textContent = 'Disconnected';
        connectionText.className = 'text-[10px] font-bold tracking-wider text-red-400 uppercase';
        connectionBadge.className = 'flex items-center gap-2 px-3 py-1 rounded-full border border-red-500/30 bg-red-950/20';
        connectionDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-red-500';
        connectionPing.className = 'hidden';
    }
}

// Load libraries
async function loadLibraries() {
    try {
        const response = await fetch('/api/libraries');
        libraries = await response.json();
        renderLibraries(libraries);
    } catch (error) {
        console.error('Failed to load libraries:', error);
        libraryList.innerHTML = `
      <li class="px-4 py-2 text-sm text-red-400">
        <i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed to load
      </li>
    `;
    }
}

function renderLibraries(libs) {
    if (libs.length === 0) {
        libraryList.innerHTML = `
      <li class="px-4 py-2 text-sm text-gray-500">
        No libraries found
      </li>
    `;
        return;
    }

    libraryList.innerHTML = libs.map(lib => {
        const safeLibrary = escapeHtml(lib.library);
        const safeLibraryAttr = safeLibrary.replace(/'/g, "\\'");
        const safeVersion = lib.versions.length > 0 ? escapeHtml(lib.versions[0]) : '';
        return `
    <li>
      <a 
        class="library-item flex items-center justify-between px-4 py-2 text-sm text-sage-textMuted hover:text-white rounded-md cursor-pointer ${currentLibrary === lib.library ? 'active' : ''}"
        onclick="selectLibrary('${safeLibraryAttr}')"
      >
        <div class="flex items-center gap-3">
          <i class="fa-solid fa-book w-4 text-center"></i>
          <span class="library-name">${safeLibrary}</span>
        </div>
        <span class="text-xs text-gray-600">${safeVersion}</span>
      </a>
    </li>
  `;
    }).join('');
}

function filterLibraries() {
    const filter = libraryFilter.value.toLowerCase();
    const filtered = libraries.filter(lib =>
        lib.library.toLowerCase().includes(filter)
    );
    renderLibraries(filtered);
}

function selectLibrary(library) {
    currentLibrary = library;
    activeFilterSection.classList.remove('hidden');
    activeFilterName.textContent = library;
    breadcrumbCurrent.textContent = library;
    renderLibraries(libraries);

    // Auto search if there's a query
    if (searchInput.value.trim()) {
        performSearch();
    }
}

function clearLibraryFilter() {
    currentLibrary = null;
    activeFilterSection.classList.add('hidden');
    breadcrumbCurrent.textContent = 'Search';
    renderLibraries(libraries);

    // Re-search if there's a query
    if (searchInput.value.trim()) {
        performSearch();
    }
}

function showAllLibraries() {
    clearLibraryFilter();
    libraryFilter.value = '';
    renderLibraries(libraries);
}

function clearSearch() {
    searchInput.value = '';
    currentLibrary = null;
    activeFilterSection.classList.add('hidden');
    breadcrumbCurrent.textContent = 'Search';
    renderLibraries(libraries);
    showEmptyState();
}

// Search functionality
async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    hideSuggestions();
    showLoadingState();

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                library: currentLibrary,
                limit: 10,
                fusion: fusionMethod.value
            })
        });

        const results = await response.json();
        renderResults(results);
    } catch (error) {
        console.error('Search failed:', error);
        showError('Search failed. Please try again.');
    }
}

async function showSuggestions(query) {
    try {
        const response = await fetch('/api/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, limit: 3 })
        });

        const suggestions = await response.json();

        if (suggestions.length > 0) {
            suggestionList.innerHTML = suggestions.map((s, i) => {
                const safeLibrary = escapeHtml(s.library);
                const safeLibraryAttr = safeLibrary.replace(/'/g, "\\'");
                return `
        <li 
          class="suggestion-item flex items-center justify-between px-4 py-3 rounded-lg cursor-pointer ${i === 0 ? 'bg-[#1f2937] border border-cyan-900/30' : ''}"
          onclick="selectLibrary('${safeLibraryAttr}'); performSearch();"
        >
          <div class="flex items-center gap-3">
            <i class="fa-solid fa-arrow-right ${i === 0 ? 'text-sage-accent' : 'text-gray-600'}"></i>
            <span class="text-sm ${i === 0 ? 'font-medium text-white' : 'text-gray-300'}">
              Search in <span class="${i === 0 ? 'text-cyan-400 font-bold' : ''}">${safeLibrary}</span>
            </span>
          </div>
          ${i === 0 ? '<span class="text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 px-2 py-0.5 rounded shadow-sm">Best Match</span>' : `<span class="text-xs text-gray-600">${s.doc_count} docs</span>`}
        </li>
      `;
            }).join('');

            searchSuggestions.classList.remove('hidden');
        } else {
            hideSuggestions();
        }
    } catch (error) {
        console.error('Failed to get suggestions:', error);
    }
}

function hideSuggestions() {
    searchSuggestions.classList.add('hidden');
}

function renderResults(results) {
    hideAllStates();

    if (results.length === 0) {
        showEmptyState();
        return;
    }

    resultsHeader.classList.remove('hidden');
    resultCount.textContent = `${results.length} matches`;

    resultsGrid.innerHTML = results.map((result, index) => `
    <div class="result-card fade-in-up bg-[#11151c] border border-gray-800 rounded-lg p-1 flex" style="opacity: 0;">
      <!-- Left Meta Column -->
      <div class="w-32 shrink-0 p-4 flex flex-col justify-between border-r border-gray-800/50">
        <div>
          <div class="flex items-center gap-2 mb-4 text-cyan-400 font-bold text-sm">
            <div class="w-10 h-10 rounded bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center border border-cyan-800/30">
              <i class="fa-solid fa-book text-cyan-400"></i>
            </div>
          </div>
          <div class="text-xs font-medium text-gray-300 mb-3">${result.library}</div>
          <div class="space-y-1">
            <span class="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Relevance</span>
            <div class="h-1 w-full bg-gray-800 rounded-full overflow-hidden">
              <div class="relevance-bar h-full bg-cyan-400 rounded-full shadow-[0_0_10px_rgba(34,211,238,0.5)]" style="width: ${Math.min(result.score * 100, 100)}%"></div>
            </div>
          </div>
        </div>
        <div>
          <span class="inline-flex items-center gap-1.5 px-2 py-1 badge-stable border rounded text-[10px]">
            <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span> ${result.version}
          </span>
        </div>
      </div>
      
      <!-- Right Content Column -->
      <div class="flex-1 p-5">
        <h3 class="text-lg font-medium text-white mb-2">${escapeHtml(result.title || 'Untitled')}</h3>
        <p class="text-gray-400 text-sm mb-4 leading-relaxed line-clamp-3">
          ${escapeHtml(truncateText(result.content, 200))}
        </p>
        
        <!-- Code Preview -->
        <div class="code-block">
          <span class="language-tag">${result.type || 'DOC'}</span>
          <pre><code>${highlightCode(truncateText(result.content, 300))}</code></pre>
        </div>
        
        <!-- Actions -->
        <div class="mt-4 flex items-center gap-3">
          <button 
            onclick="viewDocument('${escapeHtml(result.file_path)}')"
            class="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <i class="fa-solid fa-expand"></i> View Full Document
          </button>
          <span class="text-gray-700">|</span>
          <span class="text-xs text-gray-500">${result.file_path}</span>
        </div>
      </div>
    </div>
  `).join('');
}

async function viewDocument(filePath) {
    try {
        const response = await fetch(`/api/document?file_path=${encodeURIComponent(filePath)}`);
        const doc = await response.json();

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-8';
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

        modal.innerHTML = `
      <div class="bg-[#161b22] border border-gray-700 rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        <div class="flex items-center justify-between p-4 border-b border-gray-700">
          <div>
            <h2 class="text-lg font-semibold text-white">${escapeHtml(doc.title)}</h2>
            <p class="text-xs text-gray-500">${doc.library} v${doc.version} • ${doc.chunk_count} chunks</p>
          </div>
          <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white">
            <i class="fa-solid fa-xmark text-xl"></i>
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-6">
          <pre class="text-sm text-gray-300 whitespace-pre-wrap font-mono">${escapeHtml(doc.content)}</pre>
        </div>
      </div>
    `;

        document.body.appendChild(modal);
    } catch (error) {
        console.error('Failed to load document:', error);
    }
}

// UI State helpers
function showLoadingState() {
    hideAllStates();
    loadingState.classList.remove('hidden');
}

function showEmptyState() {
    hideAllStates();
    emptyState.classList.remove('hidden');
}

function showError(message) {
    hideAllStates();
    resultsGrid.innerHTML = `
    <div class="text-center py-16">
      <div class="w-24 h-24 mx-auto mb-6 rounded-full bg-red-900/20 flex items-center justify-center">
        <i class="fa-solid fa-exclamation-triangle text-4xl text-red-400"></i>
      </div>
      <h3 class="text-xl font-semibold text-gray-300 mb-2">Error</h3>
      <p class="text-gray-500">${message}</p>
    </div>
  `;
}

function hideAllStates() {
    emptyState.classList.add('hidden');
    loadingState.classList.add('hidden');
    resultsHeader.classList.add('hidden');
    resultsGrid.innerHTML = '';
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

f

function renderTruncationWarnings(warnings) {
    if (!warnings || warnings.length === 0) return '';
    
    const charWarnings = warnings.filter(w => w.truncation_type === 'character');
    const tokenWarnings = warnings.filter(w => w.truncation_type === 'token');
    
    let warningHtml = '<div class="mt-3 p-3 bg-yellow-950/30 border border-yellow-800/50 rounded-lg">';
    warningHtml += '<div class="flex items-start gap-2 mb-2">';
    warningHtml += '<i class="fa-solid fa-exclamation-triangle text-yellow-400 text-sm mt-0.5"></i>';
    warningHtml += '<div class="flex-1">';
    warningHtml += '<div class="text-yellow-400 font-medium text-xs mb-1">Content Truncation Warning</div>';
    
    if (charWarnings.length > 0) {
        warningHtml += `<div class="text-yellow-300/80 text-xs mb-1">• ${charWarnings.length} chunk(s) exceeded 4000 character limit and were truncated</div>`;
    }
    
    if (tokenWarnings.length > 0) {
        warningHtml += `<div class="text-yellow-300/80 text-xs mb-1">• ${tokenWarnings.length} chunk(s) exceeded 500 token limit and were truncated</div>`;
    }
    
    warningHtml += '<div class="text-yellow-300/60 text-xs mt-2">Consider breaking large sections into smaller parts for better search results.</div>';
    
    // Show details for first few warnings
    const displayWarnings = warnings.slice(0, 3);
    if (displayWarnings.length > 0) {
        warningHtml += '<div class="mt-2 space-y-1">';
        displayWarnings.forEach(w => {
            const lossPercent = Math.round(((w.original_size - w.truncated_size) / w.original_size) * 100);
            const sectionText = w.section_title ? ` "${escapeHtml(w.section_title)}"` : '';
            warningHtml += `<div class="text-yellow-300/70 text-[10px] font-mono">`;
            warningHtml += `Chunk ${w.chunk_index}${sectionText}: ${w.original_size} → ${w.truncated_size} ${w.truncation_type === 'character' ? 'chars' : 'tokens'} (${lossPercent}% lost)`;
            warningHtml += `</div>`;
        });
        warningHtml += '</div>';
        
        if (warnings.length > 3) {
            warningHtml += `<div class="text-yellow-300/50 text-[10px] mt-1">+ ${warnings.length - 3} more truncations</div>`;
        }
    }
    
    warningHtml += '</div></div></div>';
    return warningHtml;
}unction highlightCode(code) {
    if (!code) return '';

    // Basic syntax highlighting
    return escapeHtml(code)
        .replace(/\b(import|from|export|default|const|let|var|function|async|await|return|if|else|for|while|class|extends|new|try|catch|throw)\b/g, '<span class="token-keyword">$1</span>')
        .replace(/\b(true|false|null|undefined|NaN)\b/g, '<span class="token-keyword">$1</span>')
        .replace(/"([^"\\]|\\.)*"/g, '<span class="token-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="token-string">$&</span>')
        .replace(/`([^`\\]|\\.)*`/g, '<span class="token-string">$&</span>')
        .replace(/\b([A-Z][a-zA-Z0-9]*)\b/g, '<span class="token-class">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="token-number">$1</span>')
        .replace(/(\/\/.*$)/gm, '<span class="token-comment">$1</span>')
        .replace(/(#.*$)/gm, '<span class="token-comment">$1</span>');
}
