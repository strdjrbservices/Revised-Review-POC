// Appraisal QC Interactive Application Controller

function switchTab(tabKey) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
    });

    // Deactivate all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Activate selected
    const targetContent = document.getElementById(`tabContent-${tabKey}`);
    const targetBtn = document.getElementById(`tabBtn-${tabKey}`);

    if (targetContent) targetContent.classList.remove('hidden');
    if (targetBtn) targetBtn.classList.add('active');

    // Update URL hash
    window.location.hash = `tab-${tabKey}`;

    // Refresh icons
    if (window.lucide) {
        lucide.createIcons();
    }
}

function setFieldView(viewMode) {
    const btnNew = document.getElementById('viewBtn-new');
    const btnThree = document.getElementById('viewBtn-threeway');
    const btnOld = document.getElementById('viewBtn-old');

    const colOldHeader = document.getElementById('colHeaderOld');
    const oldCells = document.querySelectorAll('.col-old');
    const reportCells = document.querySelectorAll('.report-val-display');

    // Reset button styles
    [btnNew, btnThree, btnOld].forEach(b => {
        if (b) {
            b.classList.remove('bg-white', 'text-slate-900', 'shadow-2xs', 'font-semibold');
            b.classList.add('text-slate-600');
        }
    });

    if (viewMode === 'new') {
        btnNew.classList.add('bg-white', 'text-slate-900', 'shadow-2xs', 'font-semibold');
        if (colOldHeader) colOldHeader.classList.add('hidden');
        oldCells.forEach(c => c.classList.add('hidden'));
        document.getElementById('colHeaderReport').textContent = "Value from Report (PDF/XML)";
    } else if (viewMode === 'threeway') {
        btnThree.classList.add('bg-white', 'text-slate-900', 'shadow-2xs', 'font-semibold');
        if (colOldHeader) colOldHeader.classList.remove('hidden');
        oldCells.forEach(c => c.classList.remove('hidden'));
        document.getElementById('colHeaderReport').textContent = "Value from Revised Report";
    } else if (viewMode === 'old') {
        btnOld.classList.add('bg-white', 'text-slate-900', 'shadow-2xs', 'font-semibold');
        if (colOldHeader) colOldHeader.classList.add('hidden');
        oldCells.forEach(c => c.classList.add('hidden'));
        document.getElementById('colHeaderReport').textContent = "Value from Old Report (269-03093.xml)";
    }
}

function filterFieldRows() {
    const filter = document.getElementById('fieldFilterSelect').value;
    const rows = document.querySelectorAll('.field-row');

    rows.forEach(row => {
        const status = row.getAttribute('data-status');
        const changed = row.getAttribute('data-changed') === 'true';

        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'match') {
            row.style.display = (status === 'match') ? '' : 'none';
        } else if (filter === 'mismatch') {
            row.style.display = (status === 'mismatch') ? '' : 'none';
        } else if (filter === 'changed') {
            row.style.display = changed ? '' : 'none';
        }
    });
}

function filterDiffTable() {
    const query = (document.getElementById('diffSearchInput').value || '').toLowerCase();
    const category = document.getElementById('diffCategoryFilter').value;
    const rows = document.querySelectorAll('.diff-row');

    rows.forEach(row => {
        const rowCategory = row.getAttribute('data-category');
        const text = row.textContent.toLowerCase();

        const matchCat = (category === 'all' || rowCategory === category);
        const matchQuery = (!query || text.includes(query));

        if (matchCat && matchQuery) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function setDiffCategoryFilter(catName) {
    const select = document.getElementById('diffCategoryFilter');
    if (select) {
        select.value = catName;
        filterDiffTable();
    }
}

function toggleRawRejectionText() {
    const el = document.getElementById('rawRejectionContainer');
    if (el) {
        el.classList.toggle('hidden');
    }
}

// Checklist AJAX updates
async function toggleChecklistItem(itemId, isChecked) {
    try {
        const resp = await fetch(`/api/checklist/toggle/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_verified: isChecked })
        });
        const data = await resp.json();
        if (data.success) {
            updateChecklistUI(data);
        }
    } catch (e) {
        console.error("Failed to update checklist item:", e);
    }
}

async function saveChecklistNote(itemId, notes) {
    try {
        await fetch(`/api/checklist/toggle/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ notes: notes })
        });
    } catch (e) {
        console.error("Failed to save note:", e);
    }
}

function updateChecklistUI(data) {
    const quickPct = document.getElementById('quickChecklistPct');
    const metricRatio = document.getElementById('metricChecklistRatio');
    const metricPctBadge = document.getElementById('metricChecklistPctBadge');
    const tabBadge = document.getElementById('tabChecklistBadge');
    const statusPill = document.getElementById('checklistStatusPill');

    if (quickPct) quickPct.textContent = `${data.percent}%`;
    if (metricRatio) metricRatio.textContent = `${data.verified_count}/${data.total_count}`;
    if (metricPctBadge) metricPctBadge.textContent = `${data.percent}% Complete`;
    if (tabBadge) tabBadge.textContent = `${data.verified_count}/${data.total_count}`;

    if (statusPill) {
        if (data.percent === 100) {
            statusPill.textContent = "All Checks Verified (100%)";
            statusPill.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300";
        } else {
            statusPill.textContent = `${data.verified_count}/${data.total_count} Verified`;
            statusPill.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300";
        }
    }
}

async function saveSessionReview() {
    const reviewerName = document.getElementById('reviewerNameInput').value;
    const qcStatus = document.getElementById('qcStatusSelect').value;
    const reviewerNotes = document.getElementById('reviewerNotesInput').value;
    const saveBtn = document.getElementById('btnSaveReview');

    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = `<span>Saving...</span>`;
    saveBtn.disabled = true;

    try {
        const urlParams = new URLSearchParams(window.location.search);
        const currentSessionId = urlParams.get('session_id') || 'default';
        const resp = await fetch(`/api/session/update/${currentSessionId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                reviewer_name: reviewerName,
                qc_status: qcStatus,
                reviewer_notes: reviewerNotes
            })
        });
        const data = await resp.json();
        if (data.success) {
            saveBtn.innerHTML = `<span>✓ Saved Successfully</span>`;
            saveBtn.classList.replace('bg-sky-600', 'bg-emerald-600');
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.classList.replace('bg-emerald-600', 'bg-sky-600');
                saveBtn.disabled = false;
                if (window.lucide) lucide.createIcons();
            }, 2000);

            // Update top header badge
            const headerBadge = document.getElementById('headerQcStatusBadge');
            if (headerBadge) {
                if (qcStatus === 'APPROVED') {
                    headerBadge.textContent = "Approved for Delivery";
                    headerBadge.className = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300";
                } else {
                    headerBadge.textContent = qcStatus;
                    headerBadge.className = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300";
                }
            }
        }
    } catch (e) {
        alert("Failed to save review sign-off: " + e.message);
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
}

// Check initial hash on load
window.addEventListener('DOMContentLoaded', () => {
    const hash = window.location.hash;
    if (hash && hash.startsWith('#tab-')) {
        const tabKey = hash.replace('#tab-', '');
        switchTab(tabKey);
    }
});

