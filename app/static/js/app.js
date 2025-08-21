// ===== static/js/app.js =====
(() => {
  console.log("✅ app.js loaded");

  // -----------------------------
  // Event Listener for DOMContentLoaded
  // All code that interacts with the DOM should be inside this.
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 DOM fully loaded and parsed");
    
    // -----------------------------
    // Mobile Navigation Toggle
    // -----------------------------
    const navToggleBtn = document.getElementById('mobile-nav-toggle');
    const sidebar = document.querySelector('.sidebar');

    if (navToggleBtn && sidebar) {
      console.log("Found mobile navigation elements.");
      navToggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('nav-open');
      });
    }

    // -----------------------------
    // Dispatch Page - Status Filter
    // -----------------------------
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
      const availableList = document.querySelector('.dispatch-list[data-venue="available"]');
      const staffCountSpan = document.getElementById('available-staff-count');

      if (availableList && staffCountSpan) {
        statusFilter.addEventListener('change', () => {
          const selectedStatus = statusFilter.value;
          const staffCards = availableList.querySelectorAll('.dispatch-card');
          let visibleCount = 0;

          staffCards.forEach(card => {
            const cardStatus = card.dataset.status;
            if (selectedStatus === 'all' || cardStatus === selectedStatus) {
              card.style.display = 'flex';
              visibleCount++;
            } else {
              card.style.display = 'none';
            }
          });

          staffCountSpan.textContent = visibleCount;
        });
      }
    }

    // -----------------------------
    // Staff List Page - Status Filter (NEW)
    // -----------------------------
    const staffStatusFilter = document.getElementById('staffStatusFilter');
    if (staffStatusFilter) {
        staffStatusFilter.addEventListener('change', () => {
            const selectedStatus = staffStatusFilter.value;

            // Filter both grid cards and list rows
            const staffItems = document.querySelectorAll('#staff-grid-view .staff-card, #staff-list-view tr[data-id]');

            staffItems.forEach(item => {
                const itemStatus = item.dataset.status;
                if (selectedStatus === 'all' || itemStatus === selectedStatus) {
                    // Restore original display style (flex for cards, table-row for rows)
                    item.style.display = ''; 
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    // -----------------------------
    // Staff List: View Switcher & Sortable Initialization
    // -----------------------------
    const viewContainer = document.getElementById('staff-view-container');
    if (viewContainer) {
        console.log("Found staff view container. Initializing view switcher.");
        const gridView = document.getElementById('staff-grid-view');
        const listView = document.getElementById('staff-list-view');
        const gridBtn = document.getElementById('view-grid-btn');
        const listBtn = document.getElementById('view-list-btn');
        let sortableInstance = null;

        if (!gridView || !listView || !gridBtn || !listBtn) {
            console.error("Could not find all required elements for view switcher (grid/list views and buttons).");
            return;
        }

        const setView = (view) => {
            // This function now ONLY sets the classes, it doesn't save or reload
            console.log(`Setting view to: ${view}`);
            if (view === 'grid') {
                listView.classList.add('view-hidden');
                gridView.classList.remove('view-hidden');
                listBtn.classList.remove('active');
                gridBtn.classList.add('active');
                
                if (window.Sortable && window.innerWidth > 768 && !sortableInstance) {
                    sortableInstance = new Sortable(gridView, { 
                        animation: 150, 
                        ghostClass: "sortable-ghost", 
                        dragClass: "sortable-drag" 
                    });
                }
            } else { // 'list'
                gridView.classList.add('view-hidden');
                listView.classList.remove('view-hidden');
                gridBtn.classList.remove('active');
                listBtn.classList.add('active');
                
                if (sortableInstance) {
                    sortableInstance.destroy();
                    sortableInstance = null;
                }
            }
        };

        // NEW: Click handlers that save the choice and then reload the page
        gridBtn.addEventListener('click', () => {
            localStorage.setItem('staffView', 'grid');
            window.location.reload();
        });

        listBtn.addEventListener('click', () => {
            localStorage.setItem('staffView', 'list');
            window.location.reload();
        });

        // This part remains the same. It runs ONCE on page load to set the correct view.
        const preferredView = localStorage.getItem('staffView') || 'list';
        setView(preferredView);
    }

    // -----------------------------
    // Staff List: Status Changer (NEW)
    // -----------------------------
    const gridViewForStatusChange = document.getElementById('staff-grid-view');
    if (gridViewForStatusChange) {
        gridViewForStatusChange.addEventListener('change', async (e) => {
            if (!e.target.classList.contains('status-changer-select')) {
                return; // Ignore if the change is not from our select
            }

            const selectElement = e.target;
            const profileId = selectElement.dataset.id;
            const newStatus = selectElement.value;
            const staffCard = selectElement.closest('.staff-card');

            try {
                // CORRECTED: Added /staff prefix
                const response = await fetch(`/staff/api/profile/${profileId}/status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: newStatus }),
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.message || 'Failed to update status.');
                }

                // Update visual style
                const newStatusClass = newStatus.toLowerCase().replace(' ', '-');
                selectElement.classList.remove('status-active', 'status-working', 'status-quiet');
                selectElement.classList.add(`status-${newStatusClass}`);

                if (staffCard) {
                    staffCard.dataset.status = newStatusClass;
                }

                console.log(data.message); 

            } catch (error) {
                console.error('Error updating status:', error);
                alert(`Error: ${error.message}`);
            }
        });
    }

/// -----------------------------
// NEW: Dispatch from Staff List (Now with Venue Choice Modal)
// -----------------------------
const staffListTable = document.querySelector(".staff-list-table");
const venueChoiceModal = document.getElementById('venueChoiceModal');

if (staffListTable && venueChoiceModal) {
    const venueChoiceStaffName = document.getElementById('venueChoiceStaffName');
    const venueChoiceButtons = venueChoiceModal.querySelector('.venue-choice-buttons');
    const closeVenueChoiceBtn = document.getElementById('closeVenueChoiceModalBtn');

    let staffToDispatch = {}; 

    const openVenueChoiceModal = (staffId, staffName) => {
        staffToDispatch = { id: staffId, name: staffName };
        venueChoiceStaffName.textContent = staffName;
        venueChoiceModal.classList.remove('hidden');
    };

    const closeVenueChoiceModal = () => {
        venueChoiceModal.classList.add('hidden');
    };

    staffListTable.addEventListener('click', (e) => {
        const dispatchBtn = e.target.closest('.dispatch-from-list-btn');
        if (!dispatchBtn) return;

        const staffId = dispatchBtn.dataset.id;
        const staffName = dispatchBtn.dataset.name;
        openVenueChoiceModal(staffId, staffName);
    });

    venueChoiceButtons.addEventListener('click', (e) => {
        const venueBtn = e.target.closest('button[data-venue]');
        if (!venueBtn) return;
        const selectedVenue = venueBtn.dataset.venue;
        closeVenueChoiceModal();
        if (typeof window.openAssignmentModal === "function") {
            window.openAssignmentModal(staffToDispatch.id, staffToDispatch.name, selectedVenue);
        } else {
            alert("Error: Assignment modal function not found.");
        }
    });

    closeVenueChoiceBtn.addEventListener('click', closeVenueChoiceModal);
}

// -----------------------------
// Dispatch board: DnD + Create assignment modal
// -----------------------------
const lists = document.querySelectorAll(".dispatch-list");
if (lists.length && window.Sortable) {
  let originalList = null;

  lists.forEach((list) => {
    new Sortable(list, {
      group: "dispatch",
      animation: 150,
      ghostClass: "dispatch-card-ghost",
      dragClass: "dispatch-card-drag",
      onStart(evt) {
        originalList = evt.from;
      },
      onEnd(evt) {
        const item = evt.item;
        const profileId = item?.dataset?.id;
        const newVenue = evt.to?.dataset?.venue;
        const staffName = item?.querySelector("strong")?.textContent || "Staff";

        if (!profileId || !newVenue) {
          originalList?.appendChild(item);
          return;
        }
        if (newVenue === "available") {
          originalList?.appendChild(item);
          alert("De-assignment will be added later. For now, you cannot move back to 'Available'.");
          return;
        }

        if (typeof window.openAssignmentModal === "function") {
          window.openAssignmentModal(profileId, staffName, newVenue);
        } else {
          alert("Assignment modal not found.");
        }
        originalList?.appendChild(item);
      },
    });
  });
}

// Modal elements (Dispatch)
const assignmentModal = document.getElementById("assignmentModal");
const form = document.getElementById("assignmentForm");
const closeBtn = document.getElementById("closeAssignmentModalBtn");
const cancelBtn = document.getElementById("cancelAssignmentModalBtn");
const staffNameSpan = document.getElementById("assignmentStaffName");
const staffIdInput = document.getElementById("assignmentStaffId");
const venueInput = document.getElementById("assignmentVenue");
const startDateInput = document.getElementById("startDate");
const contractTypeInput = document.getElementById("contractType");
const baseSalaryInput = document.getElementById("baseSalary");
const roleInput = document.getElementById("assignmentRole");
const managerInput = document.getElementById("assignmentManager");

const SALARY_DEFAULTS = {
  '1jour': 1000,
  '10jours': 10000,
  '1mois': 30000
};

async function populateAssignmentModalDropdowns() {
    try {
        // CORRECTED: Added /dispatch prefix
        const response = await fetch('/dispatch/api/assignment/form-data');
        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();

        if (data.status === 'success') {
            roleInput.innerHTML = '';
            data.roles.forEach(role => {
                const option = new Option(role, role);
                roleInput.add(option);
            });

            managerInput.innerHTML = '<option value="" disabled selected>-- Select a Manager --</option>';
            data.managers.forEach(manager => {
                const option = new Option(manager.username, manager.id);
                managerInput.add(option);
            });
        } else {
            throw new Error(data.message || 'Failed to load form data');
        }
    } catch (error) {
        console.error("Error populating assignment modal:", error);
        alert("Could not load roles and managers. Please check the console and try again.");
    }
}

function updateDefaultSalary() {
    if (!contractTypeInput) return;
    const selectedType = contractTypeInput.value;
    if (SALARY_DEFAULTS[selectedType]) {
        baseSalaryInput.value = SALARY_DEFAULTS[selectedType];
    }
}

contractTypeInput?.addEventListener('change', updateDefaultSalary);

async function openModal(staffId, staffName, venue) {
  if (!assignmentModal) return;

  staffNameSpan.textContent = staffName;
  venueInput.value = venue;
  roleInput.innerHTML = '<option>Loading...</option>';
  managerInput.innerHTML = '<option>Loading...</option>';
  assignmentModal.classList.remove("hidden");

  await populateAssignmentModalDropdowns();

  staffIdInput.value = staffId;
  startDateInput.value = new Date().toISOString().split("T")[0];

  updateDefaultSalary(); 
}
function closeModal() { 
    if (assignmentModal) {
        assignmentModal.classList.add("hidden"); 
    }
}

window.openAssignmentModal = openModal;
closeBtn?.addEventListener("click", closeModal);
cancelBtn?.addEventListener("click", closeModal);

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  const prev = submitBtn.textContent;
  submitBtn.textContent = "Creating...";

  const payload = {
    staff_id: staffIdInput.value,
    venue: venueInput.value,
    role: roleInput.value,
    managed_by_user_id: managerInput.value,
    contract_type: contractTypeInput.value,
    start_date: startDateInput.value,
    base_salary: baseSalaryInput.value,
  };

  if (!payload.role) {
    alert("Please select a role.");
    submitBtn.disabled = false;
    submitBtn.textContent = prev;
    return;
  }
  if (!payload.managed_by_user_id) {
    alert("Please select a manager.");
    submitBtn.disabled = false;
    submitBtn.textContent = prev;
    return;
  }

  try {
    // CORRECTED: Added /dispatch prefix
    const res = await fetch("/dispatch/api/assignment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || "Server error");
    closeModal();
    window.location.href = '/payroll';
  } catch (err) {
    alert(err.message || "Network error.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = prev;
  }
});

    // -----------------------------
    // Payroll: Manage Performance + End/Delete
    // -----------------------------
    const table = document.querySelector(".payroll-table");
    if (table) {
        const performanceModal = document.getElementById("editRecordModal");
        const performanceForm = document.getElementById("editRecordForm");
        const closePerfBtn = document.getElementById("closeModalBtn");
        const cancelPerfBtn = document.getElementById("cancelModalBtn");
        const assignmentIdInput = document.getElementById("assignmentId");
        const contractDaysInput = document.getElementById("contractDays");
        const contractBaseSalaryInput = document.getElementById("contractBaseSalary");
        const contractStartInput = document.getElementById("contractStart");
        const contractEndInput = document.getElementById("contractEnd");
        const modalStaffName = document.getElementById("modalStaffName");
        const modalContractBadge = document.getElementById("modalContractBadge");
        const modalRoleBadge = document.getElementById("modalRoleBadge"); 
        const recordDateInput = document.getElementById("recordDate");
        const periodText = document.getElementById("periodText");
        const arrivalInput = document.getElementById("arrivalTime");
        const departureInput = document.getElementById("departureTime");
        const drinksInput = document.getElementById("drinksSold");
        const specialInput = document.getElementById("specialCommissions");
        const bonusInput = document.getElementById("bonus");
        const malusInput = document.getElementById("malus");
        const latenessPenaltyInput = document.getElementById("latenessPenalty");
        const commissionPaidInput = document.getElementById("commissionPaid");
        const proratedBaseInput = document.getElementById("proratedBase");
        const salaryPaidInput = document.getElementById("salaryPaid");
        const barProfitInput = document.getElementById("barProfit");
        const historyBox = document.getElementById("recordHistory");
        const summaryModal = document.getElementById("contractSummaryModal");
        const closeSummaryBtn = document.getElementById("closeSummaryModalBtn");
        const summaryStaffName = document.getElementById("summaryStaffName");
        const summaryAssignmentIdInput = document.getElementById("summaryAssignmentId");
        const summaryTotalDaysWorked = document.getElementById("summaryTotalDaysWorked");
        const summaryTotalDrinks = document.getElementById("summaryTotalDrinks");
        const summaryTotalSpecialComm = document.getElementById("summaryTotalSpecialComm");
        const summaryTotalCommission = document.getElementById("summaryTotalCommission");
        const summaryTotalSalary = document.getElementById("summaryTotalSalary");
        const summaryTotalProfit = document.getElementById("summaryTotalProfit");
        const summaryPdfBtn = document.getElementById("summaryPdfBtn");
        const summaryArchiveBtn = document.getElementById("summaryArchiveBtn");
        const DRINK_STAFF = 100;
        const DRINK_BAR = 120;
        const LATE_CUTOFF = "19:30";
        const TYPE_TO_DAYS = { '1jour': 1, '1day': 1, '10jours': 10, '10days': 10, '1mois': 30, '1month': 30 };
        const toTypeKey = (v) => String(v || '').trim().toLowerCase();

        function openPerformanceModal() { performanceModal?.classList.remove("hidden"); }
        function closePerformanceModal() { performanceModal?.classList.add("hidden"); }
        function openSummaryModal() { summaryModal?.classList.remove("hidden"); }
        function closeSummaryModal() { summaryModal?.classList.add("hidden"); }

        closePerfBtn?.addEventListener("click", closePerformanceModal);
        cancelPerfBtn?.addEventListener("click", closePerformanceModal);
        closeSummaryBtn?.addEventListener("click", closeSummaryModal);

        function computePenalty(arrival) {
            if (!arrival) return 0;
            const cutoff = new Date(`1970-01-01T${LATE_CUTOFF}:00`);
            const when = new Date(`1970-01-01T${arrival}:00`);
            if (when <= cutoff) return 0;
            const minutes = Math.round((when - cutoff) / 60000);
            return minutes * 5;
        }

        function recomputeDailySummary() {
            const drinks = parseFloat(drinksInput.value) || 0;
            const special = parseFloat(specialInput.value) || 0;
            const bonus = parseFloat(bonusInput.value) || 0;
            const malus = parseFloat(malusInput.value) || 0;
            const contractDays = parseInt(contractDaysInput.value || "1", 10);
            const baseSalary = parseFloat(contractBaseSalaryInput.value || "0");
            const baseDaily = contractDays > 0 ? (baseSalary / contractDays) : 0;
            const penalty = computePenalty(arrivalInput.value);
            latenessPenaltyInput.value = penalty.toFixed(0);
            const commissionStaff = drinks * DRINK_STAFF;
            commissionPaidInput.value = commissionStaff.toFixed(0);
            proratedBaseInput.value = baseDaily.toFixed(0);
            const salaryPaid = baseDaily + bonus - malus - penalty;
            salaryPaidInput.value = salaryPaid.toFixed(0);
            const profit = (drinks * DRINK_BAR + special) - salaryPaid;
            barProfitInput.value = profit.toFixed(0);
        }
        [arrivalInput, departureInput, drinksInput, specialInput, bonusInput, malusInput].forEach(el => {
            el?.addEventListener("input", recomputeDailySummary);
        });

        async function loadRecord(assignmentId, ymd) {
            try {
                // CORRECTED: Added /payroll prefix
                const res = await fetch(`/payroll/api/performance/${assignmentId}/${ymd}`);
                const data = await res.json();
                if (data && data.record) {
                    const r = data.record;
                    arrivalInput.value = r.arrival_time || "";
                    departureInput.value = r.departure_time || "";
                    drinksInput.value = r.drinks_sold ?? 0;
                    specialInput.value = r.special_commissions ?? 0;
                    bonusInput.value = r.bonus ?? 0;
                    malusInput.value = r.malus ?? 0;
                } else {
                    [arrivalInput, departureInput].forEach(i => i.value = "");
                    [drinksInput, specialInput, bonusInput, malusInput].forEach(i => i.value = 0);
                }
            } catch (e) {
                console.error("loadRecord error", e);
            }
            recomputeDailySummary();
        }
        
        async function loadPerformanceHistory(assignmentId) {
            try {
                historyBox.innerHTML = "";
                // CORRECTED: Added /payroll prefix
                const res = await fetch(`/payroll/api/performance/${assignmentId}`);
                const data = await res.json();
                if (!data || !data.records || !data.contract) {
                    historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load contract data.</p>`;
                    return;
                }
                const list = data.records;
                const contract = data.contract;
                let originalContractDays = contract.original_days || TYPE_TO_DAYS[toTypeKey(contract.contract_type)] || contract.contract_days || 1;
                const baseDaily = originalContractDays > 0 ? (contract.base_salary / originalContractDays) : 0;
                if (list.length === 0) {
                    historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">No history yet.</p>`;
                } else {
                    const tableEl = document.createElement("table");
                    tableEl.className = 'history-table';
                    tableEl.innerHTML = `<thead><tr><th>Date</th><th>Dr</th><th>Sp.</th><th>Sal.</th><th>Com.</th><th>Profit</th></tr></thead><tbody></tbody>`;
                    const tbody = tableEl.querySelector("tbody");
                    list.sort((a, b) => (a.record_date > b.record_date ? 1 : -1));
                    list.forEach(r => {
                        const tr = document.createElement("tr");
                        const commission = (r.drinks_sold || 0) * DRINK_STAFF;
                        const salary = baseDaily + (r.bonus || 0) - (r.malus || 0) - (r.lateness_penalty || 0);
                        const profit = ((r.drinks_sold || 0) * DRINK_BAR + (r.special_commissions || 0)) - salary;
                        tr.innerHTML = `<td>${new Date(r.record_date + 'T00:00:00').toLocaleDateString('en-GB', {day:'2-digit', month:'2-digit'})}</td><td>${r.drinks_sold || 0}</td><td>${(r.special_commissions || 0).toFixed(0)}฿</td><td>${salary.toFixed(0)}฿</td><td>${commission.toFixed(0)}฿</td><td>${profit.toFixed(0)}฿</td>`;
                        tr.addEventListener("click", () => { recordDateInput.value = r.record_date; loadRecord(assignmentId, r.record_date); });
                        tbody.appendChild(tr);
                    });
                    historyBox.appendChild(tableEl);
                }
                if (list.length >= contract.contract_days) {
                    calculateAndShowSummary(assignmentId, list, contract, baseDaily);
                }
            } catch (e) {
                console.error(e);
                historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
            }
        }
        
        function calculateAndShowSummary(assignmentId, records, contract, baseDaily) {
            let totalDrinks = 0, totalSpecial = 0, totalCommission = 0, totalSalary = 0, totalProfit = 0;
            records.forEach(r => {
                const dailyDrinks = r.drinks_sold || 0;
                const dailySpecial = r.special_commissions || 0;
                const dailyCommission = dailyDrinks * DRINK_STAFF;
                const dailySalary = baseDaily + (r.bonus || 0) - (r.malus || 0) - (r.lateness_penalty || 0);
                const dailyProfit = (dailyDrinks * DRINK_BAR + dailySpecial) - dailySalary;
                totalDrinks += dailyDrinks;
                totalSpecial += dailySpecial;
                totalCommission += dailyCommission;
                totalSalary += dailySalary;
                totalProfit += dailyProfit;
            });
            summaryAssignmentIdInput.value = assignmentId;
            summaryStaffName.textContent = modalStaffName.textContent;
            summaryTotalDaysWorked.textContent = `${records.length} days`;
            summaryTotalDrinks.textContent = totalDrinks;
            summaryTotalSpecialComm.textContent = `${totalSpecial.toFixed(0)}฿`;
            summaryTotalCommission.textContent = `${totalCommission.toFixed(0)}฿`;
            summaryTotalSalary.textContent = `${totalSalary.toFixed(0)}฿`;
            summaryTotalProfit.textContent = `${totalProfit.toFixed(0)}฿`;
            const profitEl = summaryTotalProfit;
            profitEl.classList.remove('profit-positive', 'profit-negative');
            if (totalProfit > 0) profitEl.classList.add('profit-positive');
            else if (totalProfit < 0) profitEl.classList.add('profit-negative');
            openSummaryModal();
        }

        async function finalizeContract(assignmentId, status) {
            const row = document.getElementById(`assignment-row-${assignmentId}`);
            const name = row ? (row.dataset.staffName || 'this contract') : 'this contract';
            if (!confirm(`This will finalize the contract for "${name}" as ${status}. Continue?`)) return;
            try {
                // CORRECTED: Added /dispatch prefix
                const res = await fetch(`/dispatch/api/assignment/${assignmentId}/finalize`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.message || "Server error");
                closeSummaryModal();
                closePerformanceModal();
                if (row) {
                    row.classList.remove('status-ongoing');
                    row.classList.add(`status-${status}`);
                    row.dataset.currentStatus = status;
                    const actionsCell = row.querySelector('.actions');
                    if(actionsCell) actionsCell.innerHTML = `<span class="status-badge status-badge-archived">Archived</span><button class="button button-secondary manage-performance-btn">View Details</button>`;
                }
                alert(`Contract for ${name} has been ${status}.`);
            } catch (err) {
                alert(`Error: ${err.message || "Network error"}`);
            }
        }
        
        summaryArchiveBtn?.addEventListener('click', () => finalizeContract(summaryAssignmentIdInput.value, 'archived'));

        summaryPdfBtn?.addEventListener('click', () => {
            const assignmentId = summaryAssignmentIdInput.value;
            if (assignmentId) {
                // CORRECTED: Added /payroll prefix
                const pdfUrl = `/payroll/assignment/${assignmentId}/pdf`;
                window.open(pdfUrl, '_blank');
            } else {
                alert('Error: Could not determine the Assignment ID.');
            }
        });

        table.addEventListener("click", async (e) => {
            const tr = e.target.closest("tr[data-assignment-id]");
            if (!tr) return;
            const assignmentId = tr.dataset.assignmentId;
            const staffName = tr.dataset.staffName;

            if (e.target.closest(".manage-performance-btn")) {
                const startIso = tr.dataset.startDate, endIso = tr.dataset.endDate;
                assignmentIdInput.value = assignmentId;
                contractDaysInput.value = String(tr.dataset.contractDays || "1");
                contractBaseSalaryInput.value = String(tr.dataset.baseSalary || "0");
                contractStartInput.value = startIso;
                contractEndInput.value = endIso;
                modalStaffName.textContent = staffName || "";
                const cType = (tr.dataset.contractType || "").trim();
                modalContractBadge.textContent = cType === "1jour" ? "1-day" : (cType === "10jours" ? "10-days" : "1-month");
                modalContractBadge.className = "contract-badge badge-" + cType;
                const role = tr.dataset.role || "";
                if (modalRoleBadge) {
                    modalRoleBadge.textContent = role;
                    modalRoleBadge.style.display = role ? 'inline-block' : 'none';
                }
                recordDateInput.min = startIso;
                recordDateInput.max = endIso;
                recordDateInput.value = startIso;
                periodText.textContent = `${startIso} → ${endIso}`;
                openPerformanceModal();
                await loadRecord(assignmentId, recordDateInput.value);
                await loadPerformanceHistory(assignmentId);
                return;
            }

            if (e.target.closest(".end-contract-btn")) {
                if (!confirm(`This will end the contract for "${staffName}" today and open the final summary. Continue?`)) return;
                try {
                    // CORRECTED: Added /dispatch prefix
                    const res = await fetch(`/dispatch/api/assignment/${assignmentId}/end`, { method: "POST" });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data.message || "Server error");
                    tr.dataset.endDate = data.assignment.end_date;
                    tr.dataset.contractDays = data.contract_days;
                    tr.querySelector('.manage-performance-btn')?.click();
                } catch (err) {
                    alert(err.message || "Network error");
                }
                return;
            }

            if (e.target.closest(".delete-contract-btn")) {
                if (!confirm(`Delete this contract for "${staffName}"? This cannot be undone.`)) return;
                try {
                    // CORRECTED: Added /dispatch prefix
                    const res = await fetch(`/dispatch/api/assignment/${assignmentId}`, { method: "DELETE" });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        throw new Error(data.message || "Server error");
                    }
                    tr.style.transition = "opacity .25s ease";
                    tr.style.opacity = "0";
                    setTimeout(() => tr.remove(), 250);
                } catch (err) {
                    alert(err.message || "Network error");
                }
                return;
            }
        });

        performanceForm?.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                assignment_id: parseInt(assignmentIdInput.value, 10),
                record_date: recordDateInput.value,
                arrival_time: arrivalInput.value || null,
                departure_time: departureInput.value || null,
                drinks_sold: parseInt(drinksInput.value || "0", 10),
                special_commissions: parseFloat(specialInput.value || "0"),
                bonus: parseFloat(bonusInput.value || "0"),
                malus: parseFloat(malusInput.value || "0"),
            };
            const submitBtn = performanceForm.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = "Saving…";
            try {
                // CORRECTED: Added /payroll prefix
                const res = await fetch("/payroll/api/performance", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.message || "Server error");
                alert("Saved successfully");
                await loadRecord(payload.assignment_id, payload.record_date);
                await loadPerformanceHistory(payload.assignment_id);
            } catch (err) {
                alert(err.message || "Network error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Save Record";
            }
        });

        recordDateInput?.addEventListener("change", () => {
            const aId = assignmentIdInput.value;
            const day = recordDateInput.value;
            if (aId && day) loadRecord(aId, day);
        });
    }

  });
  
  document.body.addEventListener("click", (e) => {
    const getTargetData = (el) => {
        const btn = el.closest(".card-delete-button, .button.button-danger");
        if (!btn) return null;
        let id = btn.dataset.id;
        let name = btn.dataset.name;
        if (!name) {
            const card = btn.closest("[data-id]");
            if (card) name = card.querySelector(".staff-card-name h3, strong")?.textContent.trim();
        }
        return { btn, id, name };
    };

    const info = getTargetData(e.target);
    if (!info) return;

    e.preventDefault();
    const { id, name } = info;
    if (!id) return;

    if (!confirm(`Delete "${name || "this profile"}"? This cannot be undone.`)) return;

    // CORRECTED: Added /staff prefix
    fetch(`/staff/api/profile/${id}/delete`, { method: "POST" })
      .then(async (r) => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok || data.status !== "success") throw new Error(data.message || "Server error");
        if (location.pathname.startsWith(`/staff/profile/${id}`)) {
          location.href = "/staff/";
          return;
        }
        document.querySelector(`.staff-card[data-id="${id}"]`)?.remove();
        document.querySelector(`tr[data-id="${id}"]`)?.remove();
      })
      .catch((err) => {
        console.error(err);
        alert("Error deleting profile.");
      });
  });

})();