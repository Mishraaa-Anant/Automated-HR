const API_URL = "/api";

// Navigation
function switchTab(tabId) {
    document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav li').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');
    document.querySelector(`.nav li[onclick="switchTab('${tabId}')"]`).classList.add('active');
}

// File Upload Logic
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
let selectedFiles = [];

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#4f46e5';
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#e2e8f0';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#e2e8f0';
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

function handleFiles(files) {
    selectedFiles = Array.from(files);
    const list = document.getElementById('fileList');
    list.innerHTML = selectedFiles.map(f => `
        <div style="padding: 10px; background: #f8fafc; border-bottom: 1px solid #eee;">
            📄 ${f.name} <span style="float:right; color:#666;">${(f.size / 1024).toFixed(1)} KB</span>
        </div>
    `).join('');
}

// Analysis Logic
// Analysis Logic
async function startAnalysis() {
    if (selectedFiles.length === 0) {
        alert("Please upload at least one resume.");
        return;
    }

    const btn = document.querySelector('.btn-primary');
    btn.innerHTML = "⏳ Uploading & Processing...";
    btn.disabled = true;

    try {
        // 1. Upload
        const formData = new FormData();
        selectedFiles.forEach(file => formData.append('files', file));

        await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });

        // 2. Trigger Analysis
        const requestData = {
            job_title: document.getElementById('jobTitle').value,
            job_description: document.getElementById('jobDesc').value,
            top_n: parseInt(document.getElementById('topN').value),
            auto_email: false // Force manual email for this flow
        };

        btn.innerHTML = "🧠 Analyzing candidates...";

        const analyzeRes = await fetch(`${API_URL}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        const result = await analyzeRes.json();

        if (analyzeRes.ok) {
            alert(`Analysis Complete! ${result.total_candidates} candidates processed.`);
            loadResults();
            switchTab('candidates');
        } else {
            alert("Analysis failed: " + result.detail);
        }

    } catch (err) {
        console.error(err);
        alert("An error occurred. check console.");
    } finally {
        btn.innerHTML = "🚀 Start Analysis";
        btn.disabled = false;
    }
}

// State
let currentCandidates = [];
let showShortlistedOnly = true;
let selectedCandidateIds = new Set();

// Load Results
async function loadResults() {
    try {
        const res = await fetch(`${API_URL}/results`);
        currentCandidates = await res.json();
        renderTable();
    } catch (err) {
        console.error("Failed to load results", err);
    }
}

// Checkbox Logic
function toggleSelectAll() {
    const isChecked = document.getElementById('selectAll').checked;
    const checkboxes = document.querySelectorAll('.candidate-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = isChecked;
        if (isChecked) selectedCandidateIds.add(cb.value);
        else selectedCandidateIds.delete(cb.value);
    });
}

function toggleSelection(id) {
    const cb = document.querySelector(`.candidate-checkbox[value="${id}"]`);
    if (cb.checked) selectedCandidateIds.add(id);
    else selectedCandidateIds.delete(id);
}

// Render Table with Filters
function renderTable() {
    const tbody = document.getElementById('candidateBody');

    // Filter
    const filtered = showShortlistedOnly
        ? currentCandidates.filter(c => c.is_shortlisted)
        : currentCandidates;

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:2rem; color:#666;">No candidates found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(c => `
        <tr>
            <td><input type="checkbox" class="candidate-checkbox" value="${c.id}" onchange="toggleSelection('${c.id}')" ${selectedCandidateIds.has(c.id) ? 'checked' : ''}></td>
            <td>
                <div style="font-weight:600;">${c.name}</div>
                <div style="font-size:0.8rem; color:#666;">${c.job_role || 'General'}</div>
                <a href="mailto:${c.email}" style="font-size:0.75rem; color:#4f46e5;">${c.email}</a>
            </td>
            <td>
                <div style="margin-bottom:4px;">
                    <span class="badge ${c.email_status === 'sent' ? 'badge-success' : 'badge-pending'}">
                        Email: ${c.email_status}
                    </span>
                </div>
                <div>
                    <span class="badge ${c.test_status === 'completed' ? 'badge-success' : 'badge-pending'}" style="background:${c.test_status === 'completed' ? '#dcfce7' : '#f3f4f6'}; color:${c.test_status === 'completed' ? '#166534' : '#4b5563'}">
                        Test: ${c.test_status}
                    </span>
                </div>
            </td>
            <td>
                <div style="font-weight:bold; color:#4f46e5;">${c.ats_score}%</div>
            </td>
            <td>
                <div style="font-weight:bold;">${Math.round(c.mcq_score)}%</div>
            </td>
            <td>
                <input type="number" min="0" max="10" step="0.5" value="${c.hr_score || 0}" 
                    style="width: 60px; padding: 4px; border: 1px solid #d1d5db; border-radius: 4px;"
                    onblur="saveHRScore('${c.id}', this.value)">
                <span style="font-size:0.8rem; color:#888;">/10</span>
            </td>
            <td>
                <div style="font-weight:bold; font-size:1.1rem; color:#0f172a;">${c.final_score || 0}/10</div>
            </td>
            <td>
                ${c.interview_time ? new Date(c.interview_time).toLocaleString() : '<span style="color:#aaa">Not Scheduled</span>'}
                ${c.meeting_link ? `<div style="margin-top:4px;"><a href="${c.meeting_link}" target="_blank" class="link-btn" style="font-size:0.75rem;">Join Call</a></div>` : ''}
            </td>
            <td style="text-align: center;">
                <button class="btn-icon delete-btn" onclick="deleteCandidate('${c.id}')" title="Delete from history" style="border:none; background:none; cursor:pointer;">
                    🗑️
                </button>
            </td>
        </tr>
    `).join('');

    // Update Dashboard Metrics
    updateMetrics(currentCandidates);
    renderChart(currentCandidates);
}

function updateMetrics(candidates) {
    document.getElementById('totalCandidates').innerText = candidates.length;
    document.getElementById('shortlistedCount').innerText = candidates.filter(c => c.is_shortlisted).length;
    document.getElementById('emailsSent').innerText = candidates.filter(c => c.email_status === 'sent').length;

    // Avg Final Score (out of 10)
    const validScores = candidates.filter(c => c.final_score !== undefined && c.final_score > 0);
    const avg = validScores.reduce((a, b) => a + b.final_score, 0) / validScores.length || 0;
    document.getElementById('avgScore').innerText = avg.toFixed(1) + '/10';
}

function toggleFilter() {
    showShortlistedOnly = document.getElementById('filterCheckbox').checked;
    renderTable();
}

// Scheduling & Invites
async function scheduleSelected() {
    const time = document.getElementById('interviewTime').value;
    if (!time) {
        alert("Please select a date and time.");
        return;
    }
    if (selectedCandidateIds.size === 0) {
        alert("Please select candidates to schedule.");
        return;
    }

    try {
        const res = await fetch(`${API_URL}/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidate_ids: Array.from(selectedCandidateIds),
                interview_time: time.replace("T", " ")
            })
        });

        if (res.ok) {
            alert("Interview times updated!");
            loadResults();
        } else {
            alert("Failed to schedule.");
        }
    } catch (err) {
        console.error(err);
        alert("Error scheduling");
    }
}

async function sendInvites() {
    if (selectedCandidateIds.size === 0) {
        alert("Please select candidates to invite.");
        return;
    }

    if (!confirm(`Send interview invites to ${selectedCandidateIds.size} candidates?`)) return;

    try {
        const res = await fetch(`${API_URL}/invite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidate_ids: Array.from(selectedCandidateIds)
            })
        });

        if (res.ok) {
            const data = await res.json();
            alert(data.message);
            loadResults(); // Status updates eventually, but refresh to clear selection maybe?
            selectedCandidateIds.clear();
        } else {
            alert("Failed to send invites.");
        }
    } catch (err) {
        console.error(err);
        alert("Error sending invites");
    }
}

async function saveHRScore(id, score) {
    try {
        const res = await fetch(`${API_URL}/score/${id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hr_score: parseFloat(score) })
        });

        if (res.ok) {
            // Optimistic update or reload
            const data = await res.json();
            const candidate = currentCandidates.find(c => c.id === id);
            if (candidate) {
                candidate.hr_score = parseFloat(score);
                candidate.final_score = data.final_score;
                renderTable(); // Re-render to update final score display
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// Delete Candidate
async function deleteCandidate(id) {
    if (!confirm("Are you sure you want to delete this record? This cannot be undone.")) return;

    try {
        const res = await fetch(`${API_URL}/history/${id}`, { method: 'DELETE' });
        if (res.ok) {
            loadResults();
        } else {
            alert("Failed to delete record");
        }
    } catch (err) {
        console.error(err);
        alert("Error deleting record");
    }
}

// Charts
let chartInstance = null;
function renderChart(candidates) {
    const ctx = document.getElementById('scoreChart').getContext('2d');
    const recentCandidates = candidates.slice(0, 20);
    const scores = recentCandidates.map(c => c.final_score || c.ats_score);

    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: recentCandidates.map(c => c.name.split(' ')[0]),
            datasets: [{
                label: 'Final Score',
                data: scores,
                backgroundColor: '#4f46e5',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

// Initial Load
loadResults();
