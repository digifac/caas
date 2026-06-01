// CAAS - PDF/DOCX to Markdown Converter
// Client-side application logic

(function() {
    'use strict';

    // DOM Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const fileCount = document.getElementById('fileCount');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.getElementById('uploadForm');
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    const markdownPre = document.getElementById('markdown');
    const renderedDiv = document.getElementById('rendered');
    const rawBtn = document.getElementById('rawBtn');
    const renderedBtn = document.getElementById('renderedBtn');
    const viewToggle = document.getElementById('viewToggle');
    const docBlocks = document.getElementById('docBlocks');
    const asyncModeCheckbox = document.getElementById('asyncMode');
    const streamingModeCheckbox = document.getElementById('streamingMode');
    const taskStatus = document.getElementById('taskStatus');
    const taskSpinner = document.getElementById('taskSpinner');
    const taskStatusText = document.getElementById('taskStatusText');
    const queueInfo = document.getElementById('queueInfo');

    // Safety check: if critical elements are missing, abort
    if (!dropZone || !fileInput) {
        console.error('CAAS: Critical DOM elements not found (dropZone or fileInput)');
        return;
    }

    // State
    let currentView = 'rendered';
    let pollingInterval = null;
    let currentBatchId = null;
    let currentTaskIds = null;
    let batchResults = null;
    let selectedFiles = []; // Maintain file list in memory for proper removal support
    window.docContentMap = {};

    // View toggle functions (single-document legacy mode)
    window.showRaw = function() {
        currentView = 'raw';
        markdownPre.classList.remove('hidden');
        renderedDiv.classList.add('hidden');
        rawBtn.classList.add('active');
        renderedBtn.classList.remove('active');
    };

    window.showRendered = function() {
        currentView = 'rendered';
        markdownPre.classList.add('hidden');
        renderedDiv.classList.remove('hidden');
        renderedBtn.classList.add('active');
        rawBtn.classList.remove('active');
    };

    // Create a per-document block with its own Raw/Formatted toggle
    function createDocBlock(filename, markdownContent, success, errorMessage) {
        const block = document.createElement('div');
        block.className = 'doc-block';

        if (!success) {
            block.innerHTML = `
                <div class="doc-block-header">
                    <span class="doc-name">${escapeHtml(filename)}</span>
                </div>
                <div class="doc-block-failed">✗ ${escapeHtml(errorMessage || 'Conversion failed')}</div>
            `;
            return block;
        }

        const blockId = 'doc_' + Math.random().toString(36).substr(2, 9);
        const preId = blockId + '_pre';
        const renderedId = blockId + '_rendered';
        const rawBtnId = blockId + '_raw';
        const renderedBtnId = blockId + '_rendered_btn';

        // Store content in map for download
        docContentMap[blockId] = markdownContent;

        block.innerHTML = `
            <div class="doc-block-header">
                <span class="doc-name">${escapeHtml(filename)}</span>
                <div class="doc-actions">
                    <button id="${renderedBtnId}" class="view-toggle-btn active" data-view="rendered">Formatted</button>
                    <button id="${rawBtnId}" class="view-toggle-btn" data-view="raw">Raw</button>
                    <button class="download-btn" data-block-id="${blockId}" data-filename="${escapeHtml(filename)}" title="Download">⬇</button>
                </div>
            </div>
            <div class="doc-block-body">
                <pre id="${preId}" class="hidden">${escapeHtml(markdownContent)}</pre>
                <div class="rendered" id="${renderedId}"></div>
            </div>
        `;

        // Render markdown content
        const renderedEl = block.querySelector(`#${renderedId}`);
        renderedEl.innerHTML = marked.parse(markdownContent);

        return block;
    }

    // Event delegation for download buttons
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-btn');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        const blockId = btn.dataset.blockId;
        const filename = btn.dataset.filename;
        const text = window.docContentMap[blockId];
        if (!text) {
            console.error('No content found for block:', blockId);
            return;
        }
        const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename.replace(/\.[^.]+$/, '') + '.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Event delegation for per-document view toggle buttons
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.view-toggle-btn');
        if (!btn) return;
        e.preventDefault();
        const view = btn.dataset.view;
        const docBlock = btn.closest('.doc-block');
        if (!docBlock) return;
        const preEl = docBlock.querySelector('pre');
        const renderedEl = docBlock.querySelector('.rendered');
        const buttons = docBlock.querySelectorAll('.view-toggle-btn');

        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        if (view === 'raw') {
            preEl.classList.remove('hidden');
            renderedEl.classList.add('hidden');
        } else {
            preEl.classList.add('hidden');
            renderedEl.classList.remove('hidden');
        }
    });

    // Main view toggle buttons (single-document legacy mode)
    const mainRenderedBtn = document.getElementById('renderedBtn');
    const mainRawBtn = document.getElementById('rawBtn');
    if (mainRenderedBtn) {
        mainRenderedBtn.addEventListener('click', function() {
            window.showRendered();
        });
    }
    if (mainRawBtn) {
        mainRawBtn.addEventListener('click', function() {
            window.showRaw();
        });
    }

    // Utility: escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Render file list with remove buttons
    function renderFileList() {
        fileList.innerHTML = '';
        if (selectedFiles.length === 0) {
            fileCount.textContent = '';
            submitBtn.disabled = true;
            return;
        }
        fileCount.textContent = selectedFiles.length === 1 ? '1 file selected' : selectedFiles.length + ' files selected';
        submitBtn.disabled = false;
        selectedFiles.forEach((file, i) => {
            const item = document.createElement('div');
            item.className = 'file-list-item';
            item.innerHTML = `
                <span class="file-name-text" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                <span class="file-status" id="fileStatus${i}"></span>
                <button type="button" class="file-remove" data-index="${i}" title="Remove">&times;</button>
            `;
            fileList.appendChild(item);
        });
    }

    // Remove a file from the selection
    window.removeFile = function(index) {
        selectedFiles.splice(index, 1);
        updateFileInput();
        renderFileList();
    };

    // Event delegation for remove buttons
    fileList.addEventListener('click', function(e) {
        const btn = e.target.closest('.file-remove');
        if (!btn) return;
        e.preventDefault();
        const index = parseInt(btn.dataset.index, 10);
        window.removeFile(index);
    });

    // Update the hidden file input to reflect selectedFiles using DataTransfer
    function updateFileInput() {
        const dt = new DataTransfer();
        selectedFiles.forEach(file => dt.items.add(file));
        fileInput.files = dt.files;
    }

    // Prevent default drag-and-drop behavior on the entire page
    // (otherwise the browser opens the dropped file instead of handling it)
    document.addEventListener('dragover', (e) => { e.preventDefault(); });
    document.addEventListener('drop', (e) => { e.preventDefault(); });

    // Drag and drop handlers
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            selectedFiles = Array.from(e.dataTransfer.files);
            updateFileInput();
            renderFileList();
        }
    });
    fileInput.addEventListener('change', () => {
        selectedFiles = Array.from(fileInput.files);
        renderFileList();
    });

    // Form submission handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        submitBtn.disabled = true;
        result.style.display = 'none';
        error.style.display = 'none';
        taskStatus.className = 'task-status';
        taskStatus.style.display = 'none';
        queueInfo.textContent = '';
        currentBatchId = null;
        currentTaskIds = null;
        batchResults = null;

        const files = selectedFiles;
        const isBatch = files.length > 1;
        const isAsync = asyncModeCheckbox.checked;
        const isStreaming = streamingModeCheckbox.checked && !isBatch && !isAsync;

        // Build FormData with correct field name for the endpoint
        const formData = new FormData();
        const fieldName = isBatch ? 'files' : 'file';
        files.forEach(file => formData.append(fieldName, file));

        // Determine endpoint and URL
        const endpoint = isBatch ? '/convert/batch' : '/convert';
        let url = endpoint;
        const params = new URLSearchParams();
        if (isAsync) params.set('async', 'true');
        if (isStreaming) params.set('streaming', 'true');
        const queryString = params.toString();
        if (queryString) url = `${endpoint}?${queryString}`;

        submitBtn.textContent = isBatch ? `Converting ${files.length} files...` : 'Converting...';

        try {
            // Streaming mode: handle SSE response
            if (isStreaming) {
                await handleStreamingResponse(url, formData, files[0].name);
                return;
            }

            const res = await fetch(url, { method: 'POST', body: formData });
            if (!res.ok) {
                let errBody;
                try {
                    errBody = await res.json();
                } catch (e) {
                    errBody = { detail: await res.text() };
                }
                // Use detail (debug mode) or message or error_code for a meaningful error string
                const errMsg = errBody.detail || errBody.message || JSON.stringify(errBody);
                throw new Error(errMsg);
            }
            const data = await res.json();

            if (isAsync) {
                if (isBatch) {
                    // Batch async mode: poll batch status
                    submitBtn.textContent = 'Waiting...';
                    showTaskStatus('pending', `${data.total_files || files.length} file(s) submitted — waiting in queue...`);
                    pollBatchStatus(data.batch_id, data.tasks || []);
                } else {
                    // Single async mode: poll task status
                    submitBtn.textContent = 'Waiting...';
                    showTaskStatus('pending', 'Task submitted — waiting in queue...');
                    pollTaskStatus(data.task_id);
                }
            } else {
                if (isBatch) {
                    // Batch sync mode: show per-file results
                    displayBatchResults(data);
                } else {
                    // Single sync mode: show single doc block
                    docBlocks.innerHTML = '';
                    const block = createDocBlock(files[0].name, data.markdown, true, '');
                    docBlocks.appendChild(block);
                    markdownPre.style.display = 'none';
                    renderedDiv.style.display = 'none';
                    viewToggle.style.display = 'none';
                    docBlocks.style.display = 'flex';
                    result.style.display = 'block';
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Convert';
                }
            }
        } catch (err) {
            error.textContent = 'Error: ' + err.message;
            error.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Convert';
        }
    });

    // Display batch results
    function displayBatchResults(data) {
        const results = data.results || [];
        const succeeded = data.succeeded || 0;
        const failed = data.failed || 0;

        // Update file list with status
        results.forEach((r, i) => {
            const statusEl = document.getElementById(`fileStatus${i}`);
            if (statusEl) {
                if (r.success) {
                    statusEl.textContent = '✓ Done';
                    statusEl.style.color = '#0f5132';
                } else {
                    statusEl.textContent = '✗ Failed';
                    statusEl.style.color = '#e63946';
                    statusEl.title = r.detail || r.message || r.error_code || 'Conversion failed';
                }
            }
        });

        // Build per-document blocks
        docBlocks.innerHTML = '';
        results.forEach((r) => {
            const block = createDocBlock(
                r.filename,
                r.markdown || '',
                r.success,
                r.detail || r.message || r.error_code || 'Conversion failed'
            );
            docBlocks.appendChild(block);
        });

        // Hide single-document elements, show doc-blocks
        markdownPre.style.display = 'none';
        renderedDiv.style.display = 'none';
        viewToggle.style.display = 'none';
        docBlocks.style.display = 'flex';
        result.style.display = 'block';

        showTaskStatus(
            failed > 0 ? 'processing' : 'completed',
            `✓ Batch complete: ${succeeded} succeeded, ${failed} failed`
        );
        taskStatus.style.display = 'flex';

        submitBtn.disabled = false;
        submitBtn.textContent = 'Convert';
    }

    // Show task status indicator
    function showTaskStatus(status, message) {
        taskStatus.className = 'task-status ' + status;
        taskStatus.style.display = 'flex';
        taskStatusText.textContent = message;
        if (status === 'completed' || status === 'failed') {
            taskSpinner.style.display = 'none';
        } else {
            taskSpinner.style.display = 'block';
        }
    }

    // Poll single task status
    async function pollTaskStatus(taskId) {
        // Stop any previous polling
        if (pollingInterval) clearInterval(pollingInterval);

        pollingInterval = setInterval(async () => {
            try {
                const res = await fetch(`/task/${taskId}`);
                if (!res.ok) return;
                const data = await res.json();

                switch (data.status) {
                    case 'pending':
                        showTaskStatus('pending', 'Task waiting in queue...');
                        submitBtn.textContent = 'Waiting...';
                        break;
                    case 'processing':
                        showTaskStatus('processing', 'Converting...');
                        submitBtn.textContent = 'Converting...';
                        break;
                    case 'completed':
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                        showTaskStatus('completed', '✓ Conversion complete!');
                        taskStatus.style.display = 'none';
                        docBlocks.innerHTML = '';
                        const fileName = data.filename || 'document';
                        const block = createDocBlock(fileName, data.result.markdown, true, '');
                        docBlocks.appendChild(block);
                        markdownPre.style.display = 'none';
                        renderedDiv.style.display = 'none';
                        viewToggle.style.display = 'none';
                        docBlocks.style.display = 'flex';
                        result.style.display = 'block';
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Convert';
                        break;
                    case 'failed':
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                        const errMsg = data.detail || data.message || data.error_code || 'Unknown error';
                        showTaskStatus('failed', '✗ Failed: ' + errMsg);
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Convert';
                        break;
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 1500);
    }

    // Poll batch status
    async function pollBatchStatus(batchId, tasks) {
        currentBatchId = batchId;
        currentTaskIds = tasks.map(t => t.task_id);

        if (pollingInterval) clearInterval(pollingInterval);

        pollingInterval = setInterval(async () => {
            try {
                const res = await fetch(`/batch/${batchId}`);
                if (!res.ok) return;
                const data = await res.json();

                const results = data.results || [];
                const total = results.length;
                const completed = results.filter(r => r.status === 'completed').length;
                const failed = results.filter(r => r.status === 'failed').length;
                const processing = results.filter(r => r.status === 'processing').length;
                const pending = results.filter(r => r.status === 'pending').length;

                // Update individual file statuses
                results.forEach((r, i) => {
                    const statusEl = document.getElementById(`fileStatus${i}`);
                    if (statusEl) {
                        switch (r.status) {
                            case 'pending':
                                statusEl.textContent = '⏳ Queued';
                                statusEl.style.color = '#856404';
                                break;
                            case 'processing':
                                statusEl.textContent = '⏳ Converting';
                                statusEl.style.color = '#084298';
                                break;
                            case 'completed':
                                statusEl.textContent = '✓ Done';
                                statusEl.style.color = '#0f5132';
                                break;
                            case 'failed':
                                statusEl.textContent = '✗ Failed';
                                statusEl.style.color = '#e63946';
                                statusEl.title = r.detail || r.message || r.error_code || 'Conversion failed';
                                break;
                        }
                    }
                });

                // Update overall status
                if (processing > 0) {
                    showTaskStatus('processing', `${completed}/${total} complete — converting...`);
                    submitBtn.textContent = 'Converting...';
                } else if (pending > 0) {
                    showTaskStatus('pending', `${completed}/${total} complete — waiting in queue...`);
                    submitBtn.textContent = 'Waiting...';
                }

                // Check if all tasks are done
                if (completed + failed === total && total > 0) {
                    clearInterval(pollingInterval);
                    pollingInterval = null;

                    // Build per-document blocks
                    docBlocks.innerHTML = '';
                    results.forEach((r) => {
                        const md = (r.status === 'completed' && r.result && r.result.markdown) ? r.result.markdown : '';
                        const success = r.status === 'completed';
                        const errMsg = r.detail || r.message || r.error_code || 'Conversion failed';
                        const block = createDocBlock(r.filename, md, success, errMsg);
                        docBlocks.appendChild(block);
                    });

                    // Hide single-document elements, show doc-blocks
                    markdownPre.style.display = 'none';
                    renderedDiv.style.display = 'none';
                    viewToggle.style.display = 'none';
                    docBlocks.style.display = 'flex';
                    result.style.display = 'block';

                    showTaskStatus(
                        failed > 0 ? 'processing' : 'completed',
                        `✓ Batch complete: ${completed} succeeded, ${failed} failed`
                    );
                    taskStatus.style.display = 'flex';

                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Convert';
                }
            } catch (err) {
                console.error('Batch polling error:', err);
            }
        }, 1500);
    }

    // Handle streaming SSE response
    async function handleStreamingResponse(url, formData, filename) {
        const res = await fetch(url, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(await res.text());

        // Show streaming status
        showTaskStatus('processing', 'Streaming conversion in progress...');
        taskStatus.style.display = 'flex';
        submitBtn.textContent = 'Streaming...';

        // Accumulate markdown from SSE chunks
        let accumulatedMd = '';
        let isComplete = false;
        let hasError = false;

        // Create a streaming doc block that updates progressively
        docBlocks.innerHTML = '';
        const blockId = 'doc_' + Math.random().toString(36).substr(2, 9);
        const preId = blockId + '_pre';
        const renderedId = blockId + '_rendered';
        const rawBtnId = blockId + '_raw';
        const renderedBtnId = blockId + '_rendered_btn';

        const block = document.createElement('div');
        block.className = 'doc-block streaming';
        block.innerHTML = `
            <div class="doc-block-header">
                <span class="doc-name">${escapeHtml(filename)}</span>
                <div class="doc-actions">
                    <span class="streaming-progress" id="streamingProgress">0%</span>
                    <button id="${renderedBtnId}" class="view-toggle-btn active" data-view="rendered">Formatted</button>
                    <button id="${rawBtnId}" class="view-toggle-btn" data-view="raw">Raw</button>
                </div>
            </div>
            <div class="doc-block-body">
                <pre id="${preId}" class="hidden"></pre>
                <div class="rendered" id="${renderedId}"></div>
            </div>
        `;
        docBlocks.appendChild(block);
        docBlocks.style.display = 'flex';
        result.style.display = 'block';

        const preEl = block.querySelector(`#${preId}`);
        const renderedEl = block.querySelector(`#${renderedId}`);
        const progressEl = block.querySelector('#streamingProgress');

        // Read the SSE stream
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        try {
            while (!isComplete && !hasError) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Parse SSE events from buffer
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);

                        // Try to parse as JSON (metadata events)
                        try {
                            const event = JSON.parse(dataStr);

                            if (event.status === 'started') {
                                // Start event — just metadata
                                continue;
                            } else if (event.status === 'complete') {
                                isComplete = true;
                                if (progressEl) progressEl.textContent = '✓ Done';
                                if (progressEl) progressEl.style.color = '#0f5132';
                                block.classList.remove('streaming');
                                // Add download button on completion
                                const dlBtn = document.createElement('button');
                                dlBtn.className = 'download-btn';
                                dlBtn.dataset.blockId = blockId;
                                dlBtn.dataset.filename = filename;
                                dlBtn.textContent = '⬇';
                                dlBtn.title = 'Download';
                                block.querySelector('.doc-actions').prepend(dlBtn);
                                docContentMap[blockId] = accumulatedMd;
                                continue;
                            } else if (event.status === 'error') {
                                hasError = true;
                                if (progressEl) progressEl.textContent = '✗ Error';
                                if (progressEl) progressEl.style.color = '#e63946';
                                block.classList.remove('streaming');
                                continue;
                            }
                        } catch (e) {
                            // Not JSON — it's a markdown chunk (unescaped from SSE)
                            // Unescape SSE-encoded newlines
                            const chunk = dataStr.replace(/\\n/g, '\n');
                            accumulatedMd += chunk;

                            // Update the display progressively
                            preEl.textContent = accumulatedMd;
                            renderedEl.innerHTML = marked.parse(accumulatedMd);

                            // Update progress percentage estimate
                            if (progressEl) {
                                const pct = Math.min(99, Math.floor((accumulatedMd.length / 100) * 2));
                                progressEl.textContent = `${pct}%`;
                            }
                        }
                    }
                }
            }

            if (!hasError) {
                showTaskStatus('completed', '✓ Streaming complete!');
                taskStatus.style.display = 'flex';
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert';
            }
        } catch (err) {
            hasError = true;
            if (progressEl) progressEl.textContent = '✗ Error';
            if (progressEl) progressEl.style.color = '#e63946';
            block.classList.remove('streaming');
            error.textContent = 'Streaming error: ' + err.message;
            error.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Convert';
        }
    }

    // Container resizing
    const container = document.getElementById('container');
    const resizeHandle = document.getElementById('resizeHandle');
    let isResizing = false;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        resizeHandle.classList.add('active');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const newWidth = e.clientX - container.getBoundingClientRect().left;
        if (newWidth >= 320 && newWidth <= 1400) {
            container.style.width = newWidth + 'px';
            container.style.maxWidth = newWidth + 'px';
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });

})();
