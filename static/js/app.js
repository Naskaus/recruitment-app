// ===== static/js/app.js (CLEAN & DEDUPED) =====
(() => {
  console.log("✅ app.js loaded");

  // -----------------------------
  // Helpers
  // -----------------------------
  const showToast = (msg) => alert(msg);

  function getTargetData(el) {
    const btn = el.closest(".card-delete-button, .button.button-danger");
    if (!btn) return null;
    let id = btn.dataset.id;
    let name = btn.dataset.name;
    if (!name) {
      const card = btn.closest("[data-id]");
      if (card) {
        const h3 = card.querySelector(".staff-card-name h3, strong");
        if (h3) name = h3.textContent.trim();
      }
    }
    return { btn, id, name };
  }

  // -----------------------------
  // Profile delete (list + detail)
  // -----------------------------
  document.addEventListener("click", (e) => {
    const info = getTargetData(e.target);
    if (!info) return;

    e.preventDefault();
    const { id, name } = info;
    if (!id) return;

    if (!confirm(`Delete "${name || "this profile"}"? This cannot be undone.`)) return;

    fetch(`/api/profile/${id}/delete`, { method: "POST" })
      .then(async (r) => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok || data.status !== "success") throw new Error(data.message || "Server error");
        if (location.pathname === `/profile/${id}` || location.pathname === `/profile/${id}/`) {
          location.href = "/staff";
          return;
        }
        const card = document.querySelector(`.staff-card[data-id="${id}"]`);
        if (card) {
          card.style.transition = "opacity .25s ease";
          card.style.opacity = "0";
          setTimeout(() => card.remove(), 250);
        }
      })
      .catch((err) => {
        console.error(err);
        showToast("Error deleting profile.");
      });
  });

  // -----------------------------
  // Staff list: Sortable (optional)
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    const grid = document.querySelector(".staff-grid");
    if (grid && window.Sortable) {
      new Sortable(grid, { animation: 150, ghostClass: "sortable-ghost", dragClass: "sortable-drag" });
    }
  });

  // -----------------------------
  // Dispatch board: DnD + Create assignment modal
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    const lists = document.querySelectorAll(".dispatch-list");
    if (!lists.length || !window.Sortable) return;

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
            // Not supported yet, revert:
            originalList?.appendChild(item);
            alert("De-assignment will be added later. For now, you cannot move back to 'Available'.");
            return;
          }

          if (typeof window.openAssignmentModal === "function") {
            window.openAssignmentModal(profileId, staffName, newVenue);
          } else {
            alert("Assignment modal not found.");
          }
          // revert visually; the page will reload after creation
          originalList?.appendChild(item);
        },
      });
    });

    // Modal elements (Dispatch)
    const assignmentModal = document.getElementById("assignmentModal");
    const form = document.getElementById("assignmentForm");
    const closeBtn = document.getElementById("closeAssignmentModalBtn");
    const cancelBtn = document.getElementById("cancelAssignmentModalBtn");
    const staffNameSpan = document.getElementById("assignmentStaffName");
    const staffIdInput = document.getElementById("assignmentStaffId");
    const venueInput = document.getElementById("assignmentVenue");
    const startDateInput = document.getElementById("startDate");

    function openModal(staffId, staffName, venue) {
      staffIdInput.value = staffId;
      staffNameSpan.textContent = staffName;
      venueInput.value = venue;
      startDateInput.value = new Date().toISOString().split("T")[0];
      assignmentModal?.classList.remove("hidden");
    }
    function closeModal() { assignmentModal?.classList.add("hidden"); }

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
        contract_type: document.getElementById("contractType").value,
        start_date: startDateInput.value,
        base_salary: document.getElementById("baseSalary").value,
      };

      try {
        const res = await fetch("/api/assignment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.message || "Server error");
        closeModal();
        location.reload();
      } catch (err) {
        alert(err.message || "Network error.");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = prev;
      }
    });
  });

  // -----------------------------
  // Payroll: Manage Performance + End/Delete
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    const table = document.querySelector(".payroll-table");
    if (!table) return;

    // --- Performance Modal Elements ---
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

    // --- NEW: Summary Modal Elements ---
    const summaryModal = document.getElementById("contractSummaryModal");
    const closeSummaryBtn = document.getElementById("closeSummaryModalBtn");
    const summaryStaffName = document.getElementById("summaryStaffName");
    const summaryAssignmentIdInput = document.getElementById("summaryAssignmentId");

    const summaryTotalDrinks = document.getElementById("summaryTotalDrinks");
    const summaryTotalSpecialComm = document.getElementById("summaryTotalSpecialComm");
    const summaryTotalCommission = document.getElementById("summaryTotalCommission");
    const summaryTotalSalary = document.getElementById("summaryTotalSalary");
    const summaryTotalProfit = document.getElementById("summaryTotalProfit");
    
    const summaryPdfBtn = document.getElementById("summaryPdfBtn");
    const summaryOnHoldBtn = document.getElementById("summaryOnHoldBtn");
    const summaryArchiveBtn = document.getElementById("summaryArchiveBtn");


    // --- Constants ---
    const DRINK_STAFF = 100;
    const DRINK_BAR = 120;
    const LATE_CUTOFF = "19:30";

    // --- Modal Controls ---
    function openPerformanceModal() { performanceModal?.classList.remove("hidden"); }
    function closePerformanceModal() { performanceModal?.classList.add("hidden"); }
    function openSummaryModal() { summaryModal?.classList.remove("hidden"); }
    function closeSummaryModal() { summaryModal?.classList.add("hidden"); }

    closePerfBtn?.addEventListener("click", closePerformanceModal);
    cancelPerfBtn?.addEventListener("click", closePerformanceModal);
    closeSummaryBtn?.addEventListener("click", closeSummaryModal);

    // --- Daily Calculation Logic ---
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

    // --- Data Loading ---
    async function loadRecord(assignmentId, ymd) {
      try {
        const res = await fetch(`/api/performance/${assignmentId}/${ymd}`);
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
          // BUG FIX: Don't reset the whole form. Just clear daily fields.
          // This preserves the selected date.
          arrivalInput.value = "";
          departureInput.value = "";
          drinksInput.value = 0;
          specialInput.value = 0;
          bonusInput.value = 0;
          malusInput.value = 0;
        }
      } catch (e) {
        console.error("loadRecord error", e);
      }
      recomputeDailySummary(); // This recomputes summary fields like salary, profit, etc.
    }
    
    async function loadPerformanceHistory(assignmentId) {
      try {
        historyBox.innerHTML = "";
        const res = await fetch(`/api/performance/${assignmentId}`);
        const data = await res.json();
        
        if (!data || !data.records || !data.contract) {
            historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load contract data.</p>`;
            return;
        }

        const list = data.records;
        const contract = data.contract;

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
                const baseDaily = contract.contract_days > 0 ? (contract.base_salary / contract.contract_days) : 0;
                const penalty = r.lateness_penalty || 0;
                const bonus = r.bonus || 0;
                const malus = r.malus || 0;
                
                const commission = (r.drinks_sold || 0) * DRINK_STAFF;
                const salary = baseDaily + bonus - malus - penalty;
                const profit = ((r.drinks_sold || 0) * DRINK_BAR + (r.special_commissions || 0)) - salary;
                
                tr.innerHTML = `
                    <td>${new Date(r.record_date + 'T00:00:00').toLocaleDateString('en-GB', {day:'2-digit', month:'2-digit'})}</td>
                    <td>${r.drinks_sold || 0}</td>
                    <td>${(r.special_commissions || 0).toFixed(0)}฿</td>
                    <td>${salary.toFixed(0)}฿</td>
                    <td>${commission.toFixed(0)}฿</td>
                    <td>${profit.toFixed(0)}฿</td>
                `;
                tr.addEventListener("click", () => {
                  recordDateInput.value = r.record_date;
                  loadRecord(assignmentId, r.record_date);
                });
                tbody.appendChild(tr);
            });
            historyBox.appendChild(tableEl);
        }

        if (list.length >= contract.contract_days) {
            calculateAndShowSummary(assignmentId, list, contract);
        }

      } catch (e) {
        console.error(e);
        historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
      }
    }
    
    function calculateAndShowSummary(assignmentId, records, contract) {
        let totalDrinks = 0, totalSpecial = 0, totalCommission = 0, totalSalary = 0, totalProfit = 0;
        
        const baseDaily = contract.contract_days > 0 ? (contract.base_salary / contract.contract_days) : 0;

        records.forEach(r => {
            const dailyDrinks = r.drinks_sold || 0;
            const dailySpecial = r.special_commissions || 0;
            const dailyPenalty = r.lateness_penalty || 0;
            const dailyBonus = r.bonus || 0;
            const dailyMalus = r.malus || 0;

            const dailyCommission = dailyDrinks * DRINK_STAFF;
            const dailySalary = baseDaily + dailyBonus - dailyMalus - dailyPenalty;
            const dailyProfit = (dailyDrinks * DRINK_BAR + dailySpecial) - dailySalary;

            totalDrinks += dailyDrinks;
            totalSpecial += dailySpecial;
            totalCommission += dailyCommission;
            totalSalary += dailySalary;
            totalProfit += dailyProfit;
        });

        summaryAssignmentIdInput.value = assignmentId;
        summaryStaffName.textContent = modalStaffName.textContent;
        summaryTotalDrinks.textContent = totalDrinks;
        summaryTotalSpecialComm.textContent = `${totalSpecial.toFixed(0)}฿`;
        summaryTotalCommission.textContent = `${totalCommission.toFixed(0)}฿`;
        summaryTotalSalary.textContent = `${totalSalary.toFixed(0)}฿`;
        summaryTotalProfit.textContent = `${totalProfit.toFixed(0)}฿`;
        
        openSummaryModal();
    }

    async function finalizeContract(assignmentId, status) {
        const row = document.getElementById(`assignment-row-${assignmentId}`);
        const name = row ? (row.dataset.staffName || 'this contract') : 'this contract';

        if (!confirm(`This will finalize the contract for "${name}" with status "${status}". Continue?`)) return;

        try {
            const res = await fetch(`/api/assignment/${assignmentId}/finalize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: status })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.message || "Server error");

            closeSummaryModal();
            closePerformanceModal();
            if (row) {
                row.style.transition = "opacity .25s ease";
                row.style.opacity = "0";
                setTimeout(() => row.remove(), 250);
            }
            alert(`Contract for ${name} has been ${status}.`);

        } catch (err) {
            alert(`Error: ${err.message || "Network error"}`);
        }
    }
    
    summaryOnHoldBtn?.addEventListener('click', () => {
        const assignmentId = summaryAssignmentIdInput.value;
        finalizeContract(assignmentId, 'on_hold');
    });

    summaryArchiveBtn?.addEventListener('click', () => {
        const assignmentId = summaryAssignmentIdInput.value;
        finalizeContract(assignmentId, 'archived');
    });

    summaryPdfBtn?.addEventListener('click', () => {
        alert('PDF generation will be implemented in a future step.');
    });


    // --- Event Delegation for Payroll Table ---
    table.addEventListener("click", async (e) => {
      const tr = e.target.closest("tr[data-assignment-id]");
      if (!tr) return;

      const assignmentId = tr.dataset.assignmentId;
      const staffName = tr.dataset.staffName;

      // Manage performance
      if (e.target.closest(".manage-performance-btn")) {
        const startIso = tr.dataset.startDate;
        const endIso = tr.dataset.endDate;
        const baseSalary = parseFloat(tr.dataset.baseSalary || "0");
        const contractDays = parseInt(tr.dataset.contractDays || "1", 10);
        const cType = (tr.dataset.contractType || "").trim();

        assignmentIdInput.value = assignmentId;
        contractDaysInput.value = String(contractDays);
        contractBaseSalaryInput.value = String(baseSalary);
        contractStartInput.value = startIso;
        contractEndInput.value = endIso;
        modalStaffName.textContent = staffName || "";
        modalContractBadge.textContent = cType === "1jour" ? "1-day" : (cType === "10jours" ? "10-days" : "1-month");
        modalContractBadge.className = "contract-badge badge-" + cType;
        recordDateInput.min = startIso;
        recordDateInput.max = endIso;
        recordDateInput.value = startIso;
        periodText.textContent = `${startIso} → ${endIso}`;

        openPerformanceModal();
        
        await loadRecord(assignmentId, recordDateInput.value);
        await loadPerformanceHistory(assignmentId);
        return;
      }

      // End now
      if (e.target.closest(".end-contract-btn")) {
        if (!confirm(`End this contract now for "${staffName}"?`)) return;
        try {
          const res = await fetch(`/api/assignment/${assignmentId}/end`, { method: "POST" });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.message || "Server error");
          tr.style.transition = "opacity .25s ease";
          tr.style.opacity = "0";
          setTimeout(() => tr.remove(), 250);
        } catch (err) {
          alert(err.message || "Network error");
        }
        return;
      }

      // Delete
      if (e.target.closest(".delete-contract-btn")) {
        if (!confirm(`Delete this contract for "${staffName}"? This cannot be undone.`)) return;
        try {
          const res = await fetch(`/api/assignment/${assignmentId}`, { method: "DELETE" });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.message || "Server error");
          tr.style.transition = "opacity .25s ease";
          tr.style.opacity = "0";
          setTimeout(() => tr.remove(), 250);
        } catch (err) {
          alert(err.message || "Network error");
        }
        return;
      }
    });

    // Save (upsert) performance
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
      const oldText = submitBtn.textContent;
      submitBtn.textContent = "Saving…";

      try {
        const res = await fetch("/api/performance", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        let data = {};
        try { data = await res.json(); } catch {}

        if (!res.ok) throw new Error(data.message || "Server error");

        alert("Saved successfully");
        await loadRecord(payload.assignment_id, payload.record_date);
        await loadPerformanceHistory(payload.assignment_id);
      } catch (err) {
        alert(err.message || "Network error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = oldText;
      }
    });

    // Change date -> reload that day's record
    recordDateInput?.addEventListener("change", () => {
      const aId = assignmentIdInput.value;
      const day = recordDateInput.value;
      if (!aId || !day) return;
      loadRecord(aId, day);
    });
  });
})();