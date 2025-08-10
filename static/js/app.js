// ===== static/js/app.js (FULL REPLACEMENT) =====
(function () {
  console.log("✅ app.js loaded");

  // ----------------------------------------------
  // Small helpers
  // ----------------------------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const showToast = (msg) => alert(msg);

  // Extract id/name from delete targets (trash icon or red button)
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

  // ----------------------------------------------
  // Staff List: delete profile (trash icon + red button on detail)
  // ----------------------------------------------
  document.addEventListener("click", function (e) {
    const info = getTargetData(e.target);
    if (!info) return;

    e.preventDefault();
    const { id, name } = info;
    if (!id) return console.warn("⚠️ Delete: missing data-id");

    if (!confirm(`Delete "${name || "this profile"}"? This cannot be undone.`)) return;

    fetch(`/api/profile/${id}/delete`, { method: "POST" })
      .then(async (r) => {
        let data = {};
        try { data = await r.json(); } catch {}
        return { ok: r.ok, data };
      })
      .then(({ ok, data }) => {
        if (!ok || data.status !== "success") throw new Error(data.message || "Server error");

        // If we are on the profile detail page, go back to list
        if (window.location.pathname === `/profile/${id}` || window.location.pathname === `/profile/${id}/`) {
          window.location.href = "/staff";
          return;
        }
        // Otherwise fade out the card in the grid
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

  // ----------------------------------------------
  // Staff List: Sortable grid (purely cosmetic for now)
  // ----------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    const grid = $(".staff-grid");
    if (grid && window.Sortable) {
      new Sortable(grid, { animation: 150, ghostClass: "sortable-ghost", dragClass: "sortable-drag" });
    }
  });

  // ----------------------------------------------
  // Dispatch Board: DnD → open assignment modal → create assignment
  // ----------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    const lists = $$(".dispatch-list");
    if (!lists.length) return;
    if (!window.Sortable) {
      console.warn("⚠️ SortableJS not found on dispatch page.");
      return;
    }

    let originalList = null;
    lists.forEach((list) => {
      new Sortable(list, {
        group: "dispatch",
        animation: 150,
        ghostClass: "dispatch-card-ghost",
        dragClass: "dispatch-card-drag",
        onStart(evt) { originalList = evt.from; },
        onEnd(evt) {
          const item = evt.item;
          const profileId = item?.dataset?.id;
          const newVenue = evt.to?.dataset?.venue;
          const staffName = item?.querySelector("strong")?.textContent || "Staff";

          if (!profileId || !newVenue) {
            if (originalList) originalList.appendChild(item);
            return;
          }
          if (newVenue === "available") {
            if (originalList) originalList.appendChild(item);
            alert("De-assignment will be added later. You cannot move back to 'Available' yet.");
            return;
          }

          if (typeof window.openAssignmentModal === "function") {
            window.openAssignmentModal(profileId, staffName, newVenue);
          } else {
            alert("Assignment modal not found.");
          }
          if (originalList) originalList.appendChild(item); // revert UI; page will reload on create
        },
      });
    });

    // Modal fields
    const assignmentModal = $("#assignmentModal");
    if (!assignmentModal) return; // not on this page

    const form = $("#assignmentForm");
    const closeBtn = $("#closeAssignmentModalBtn");
    const cancelBtn = $("#cancelAssignmentModalBtn");
    const staffNameSpan = $("#assignmentStaffName");
    const staffIdInput = $("#assignmentStaffId");
    const venueInput = $("#assignmentVenue");
    const startDateInput = $("#startDate");

    function openModal(staffId, staffName, venue) {
      staffIdInput.value = staffId;
      staffNameSpan.textContent = staffName;
      venueInput.value = venue;
      startDateInput.value = new Date().toISOString().split("T")[0];
      assignmentModal.classList.remove("hidden");
    }
    function closeModal() { assignmentModal.classList.add("hidden"); }

    window.openAssignmentModal = openModal;
    closeBtn?.addEventListener("click", closeModal);
    cancelBtn?.addEventListener("click", closeModal);

    form?.addEventListener("submit", async function (e) {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating...";

      const payload = {
        staff_id: staffIdInput.value,
        venue: venueInput.value,
        contract_type: $("#contractType").value,
        start_date: startDateInput.value,
        base_salary: $("#baseSalary").value,
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
        window.location.reload();
      } catch (err) {
        alert(err.message || "Network error.");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Assignment";
      }
    });
  });

  // ----------------------------------------------
  // Payroll page: Manage Performance modal + End/Delete
  // ----------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    const table = $(".payroll-table");
    if (!table) return; // not on payroll page

    // Modal elements (IDs must match payroll.html)
    const modal = $("#editRecordModal");
    const form = $("#editRecordForm");
    const closeBtn = $("#closeModalBtn");
    const cancelBtn = $("#cancelModalBtn");

    const assignmentIdInput = $("#assignmentId");
    const contractDaysInput = $("#contractDays");
    const contractBaseSalaryInput = $("#contractBaseSalary");
    const contractStartInput = $("#contractStart");
    const contractEndInput = $("#contractEnd");

    const modalStaffName = $("#modalStaffName");
    const modalContractBadge = $("#modalContractBadge");

    const recordDateInput = $("#recordDate");
    const periodText = $("#periodText");

    const arrivalInput = $("#arrivalTime");
    const departureInput = $("#departureTime");
    const drinksInput = $("#drinksSold");
    const specialInput = $("#specialCommissions");
    const bonusInput = $("#bonus");
    const malusInput = $("#malus");

    const latenessPenaltyInput = $("#latenessPenalty");
    const commissionPaidInput = $("#commissionPaid");
    const proratedBaseInput = $("#proratedBase");
    const salaryPaidInput = $("#salaryPaid");
    const barProfitInput = $("#barProfit");

    const historyBox = $("#recordHistory");

    const DRINK_STAFF = 100;
    const DRINK_BAR = 120;
    const LATE_CUTOFF = "19:30";

    function openModal() { modal.classList.remove("hidden"); }
    function closeModal() { modal.classList.add("hidden"); }
    closeBtn?.addEventListener("click", closeModal);
    cancelBtn?.addEventListener("click", closeModal);

    function computePenalty(arrival) {
      if (!arrival) return 0;
      const cutoff = new Date(`1970-01-01T${LATE_CUTOFF}:00`);
      const when = new Date(`1970-01-01T${arrival}:00`);
      if (when <= cutoff) return 0;
      const minutes = Math.round((when - cutoff) / 60000);
      return minutes * 5; // 5 THB/min
    }

    function recompute() {
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
      el?.addEventListener("input", recompute);
    });

    // --- API: load one day + short history (server already limits)
    async function loadRecord(assignmentId, ymd) {
      historyBox.innerHTML = "";
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
          latenessPenaltyInput.value = r.lateness_penalty ?? 0;
        } else {
          arrivalInput.value = "";
          departureInput.value = "";
          drinksInput.value = 0;
          specialInput.value = 0;
          bonusInput.value = 0;
          malusInput.value = 0;
          latenessPenaltyInput.value = 0;
        }

        (data.history || []).forEach(h => {
          const d = new Date(h.record_date + "T00:00:00");
          const div = document.createElement("div");
          div.className = "history-item";
          div.innerHTML = `
            <div><span>Date:</span> <strong>${d.toLocaleDateString('en-GB')}</strong></div>
            <div><span>Drinks:</span> <strong>${h.drinks_sold ?? 0}</strong></div>
            <div><span>Penalty:</span> <strong>${(h.lateness_penalty ?? 0)} THB</strong></div>
            <div><span>—</span> <strong>&nbsp;</strong></div>
          `;
          historyBox.appendChild(div);
        });
      } catch (e) {
        console.error("loadRecord error", e);
        historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
      }
      recompute();
    }
    window.loadRecord = loadRecord; // optional global

    // --- API: load full history for the assignment (stable endpoint)
    async function loadFullHistory(assignmentId) {
      try {
        historyBox.innerHTML = "";
        const res = await fetch(`/api/performance/${assignmentId}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Server error");
        renderHistoryList(data.records || [], data.contract);
      } catch (err) {
        console.error("loadFullHistory error", err);
        historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
      }
    }
    window.loadFullHistory = loadFullHistory; // optional global

    function renderHistoryList(records, contract) {
      historyBox.innerHTML = "";
      if (!records || records.length === 0) {
        historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">No history yet.</p>`;
        return;
      }
      // sort ascending by date for readability
      records.sort((a, b) => (a.record_date > b.record_date ? 1 : -1));

      const frag = document.createDocumentFragment();
      records.forEach(r => {
        const d = new Date(r.record_date + "T00:00:00");
        const div = document.createElement("div");
        div.className = "history-item";
        div.dataset.date = r.record_date;
        div.innerHTML = `
          <div><span>Date:</span> <strong>${d.toLocaleDateString('en-GB', {day:'2-digit', month:'2-digit'})}</strong></div>
          <div><span>Drinks:</span> <strong>${r.drinks_sold ?? 0}</strong></div>
          <div><span>Penalty:</span> <strong>${(r.lateness_penalty ?? 0)} THB</strong></div>
          <div><span>Commission:</span> <strong>${((r.drinks_sold ?? 0) * 100).toFixed(0)} THB</strong></div>
        `;
        // click → load that day in the form
        div.addEventListener("click", () => {
          recordDateInput.value = r.record_date;
          loadRecord(assignmentIdInput.value, r.record_date);
        });
        frag.appendChild(div);
      });
      historyBox.appendChild(frag);

      // Add/Add-Edit Day helper button next to the date field (JS-only)
      ensureAddEditDayButton(contract);
    }

    function ensureAddEditDayButton(contract) {
      let btn = $("#addEditDayBtn");
      if (!btn) {
        btn = document.createElement("button");
        btn.id = "addEditDayBtn";
        btn.type = "button";
        btn.className = "button button-secondary";
        btn.style.marginLeft = "12px";
        btn.textContent = "Add / Edit Day";
        recordDateInput.insertAdjacentElement("afterend", btn);
      }
      btn.onclick = () => {
        const val = recordDateInput.value;
        if (!val) return alert("Please pick a date inside the contract period.");
        const today = new Date().toISOString().slice(0, 10);
        if (val > today) return alert("Future dates are not allowed.");
        if (val < contract.start_date || val > contract.end_date) {
          return alert(`Date must be within ${contract.start_date} → ${contract.end_date}.`);
        }
        loadRecord(assignmentIdInput.value, val);
      };
    }

    // --- Row actions (one delegation for all buttons)
    table.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-assignment-id]");
      if (!tr) return;

      // “Manage performance”
      if (e.target.closest(".manage-performance-btn")) {
        const aId = tr.dataset.assignmentId;
        const staffName = tr.dataset.staffName;
        const startIso = tr.dataset.startDate;
        const endIso = tr.dataset.endDate;
        const baseSalary = parseFloat(tr.dataset.baseSalary || "0");
        const contractDays = parseInt(tr.dataset.contractDays || "1", 10);
        const cType = (tr.dataset.contractType || "").trim(); // "1jour" | "10jours" | "1mois"

        assignmentIdInput.value = aId;
        contractDaysInput.value = contractDays;
        contractBaseSalaryInput.value = baseSalary.toString();
        contractStartInput.value = startIso;
        contractEndInput.value = endIso;

        modalStaffName.textContent = staffName || "";

        // Badge (supports your CSS classes)
        if (modalContractBadge) {
          modalContractBadge.textContent =
            cType === "1jour" ? "1-day" : (cType === "10jours" ? "10-days" : "1-month");
          modalContractBadge.className = "contract-badge badge-" + cType;
        }

        // Date bounds
        recordDateInput.min = startIso;
        recordDateInput.max = endIso;
        recordDateInput.value = startIso;
        periodText.textContent = `${startIso} → ${endIso}`;

        openModal();
        // Load both: full history (persistent list) + the selected day
        loadFullHistory(aId);
        loadRecord(aId, recordDateInput.value);
        return;
      }

      // End now (support two possible class names)
      if (e.target.closest(".assignment-finish-btn, .end-contract-btn")) {
        const name = tr.dataset.staffName || "this staff";
        if (!confirm(`End this contract now for "${name}"?`)) return;

        const id = tr.dataset.assignmentId;
        fetch(`/api/assignment/${id}/end`, { method: "POST" })
          .then(async (r) => {
            let data = {};
            try { data = await r.json(); } catch {}
            if (!r.ok) throw new Error(data.message || "Server error");
            tr.style.transition = "opacity .25s ease";
            tr.style.opacity = "0";
            setTimeout(() => tr.remove(), 250);
          })
          .catch((err) => alert(err.message || "Network error"));
        return;
      }

      // Delete (support two possible class names)
      if (e.target.closest(".assignment-delete-btn, .delete-contract-btn")) {
        const name = tr.dataset.staffName || "this staff";
        if (!confirm(`Delete this contract for "${name}"? This cannot be undone.`)) return;

        const id = tr.dataset.assignmentId;
        fetch(`/api/assignment/${id}`, { method: "DELETE" })
          .then(async (r) => {
            let data = {};
            try { data = await r.json(); } catch {}
            if (!r.ok) throw new Error(data.message || "Server error");
            tr.style.transition = "opacity .25s ease";
            tr.style.opacity = "0";
            setTimeout(() => tr.remove(), 250);
          })
          .catch((err) => alert(err.message || "Network error"));
        return;
      }
    });

    // Change date → reload that day
    recordDateInput?.addEventListener("change", () => {
      const aId = assignmentIdInput.value;
      const day = recordDateInput.value;
      if (!aId || !day) return;
      loadRecord(aId, day);
    });

    // Save = upsert the day, then refresh record + full history
    form?.addEventListener("submit", async (e) => {
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

      const submitBtn = form.querySelector('button[type="submit"]');
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
        // 1) refresh the selected day fields
        await loadRecord(assignmentIdInput.value, recordDateInput.value);
        // 2) refresh the persistent history list (handles “first day” case)
        await loadFullHistory(assignmentIdInput.value);
      } catch (err) {
        alert(err.message || "Network error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = oldText;
      }
    });
  });
})();
