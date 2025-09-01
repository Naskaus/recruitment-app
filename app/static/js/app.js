// ===== static/js/app.js =====
(() => {
  console.log("✅ app.js loaded");

  // NEW: CSRF Protection for all fetch requests
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const oldFetch = window.fetch;
  window.fetch = function(...args) {
    const [url, options] = args;
    const unsafeMethods = ['POST', 'PUT', 'DELETE'];

    if (options && unsafeMethods.includes(options.method)) {
      if (!options.headers) {
        options.headers = {};
      }
      // If it's a FormData request, the browser sets the Content-Type.
      // Otherwise, for our app's API, we default to application/json if not set.
      if (!(options.body instanceof FormData)) {
          if (!options.headers['Content-Type']) {
              options.headers['Content-Type'] = 'application/json';
          }
      }
      options.headers['X-CSRFToken'] = csrfToken;
    }
    return oldFetch(...args);
  };

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
    // Sidebar Dropdown Menu
    // -----------------------------
    const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
    dropdownToggles.forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.preventDefault();
        const dropdown = toggle.closest('.sidebar-dropdown');
        const dropdownContent = dropdown.querySelector('.dropdown-content');
        
        // Close other dropdowns
        document.querySelectorAll('.sidebar-dropdown').forEach(otherDropdown => {
          if (otherDropdown !== dropdown) {
            otherDropdown.classList.remove('active');
          }
        });
        
        // Toggle current dropdown
        dropdown.classList.toggle('active');
      });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.sidebar-dropdown')) {
        document.querySelectorAll('.sidebar-dropdown').forEach(dropdown => {
          dropdown.classList.remove('active');
        });
      }
    });

    // -----------------------------
    // Agency Switch Modal
    // -----------------------------
    const switchAgencyBtn = document.getElementById('switchAgencyBtn');
    const agencySwitchModal = document.getElementById('agencySwitchModal');
    const closeAgencyModalBtn = document.getElementById('closeAgencyModalBtn');
    const agencyList = document.querySelector('.agency-list');

    if (switchAgencyBtn && agencySwitchModal) {
        // Open agency switch modal
        switchAgencyBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/auth/api/agencies');
                const data = await response.json();
                
                if (response.ok) {
                    renderAgencyList(data.agencies, data.current_agency_id);
                    agencySwitchModal.classList.remove('hidden');
                } else {
                    console.error('Failed to load agencies:', data.message);
                }
            } catch (error) {
                console.error('Error loading agencies:', error);
            }
        });

        // Close modal
        closeAgencyModalBtn.addEventListener('click', () => {
            agencySwitchModal.classList.add('hidden');
        });

        // Close modal when clicking outside
        agencySwitchModal.addEventListener('click', (e) => {
            if (e.target === agencySwitchModal) {
                agencySwitchModal.classList.add('hidden');
            }
        });

        // Handle agency selection
        agencyList.addEventListener('click', async (e) => {
            const agencyItem = e.target.closest('.agency-item');
            if (!agencyItem) return;

            const agencyId = agencyItem.dataset.agencyId;
            if (!agencyId) return;

            try {
                const response = await fetch('/auth/api/switch-agency', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                    },
                    body: JSON.stringify({ agency_id: agencyId })
                });

                const data = await response.json();
                
                if (response.ok) {
                    // Update current agency display
                    const currentAgencySpan = document.querySelector('.current-agency');
                    if (currentAgencySpan) {
                        currentAgencySpan.textContent = data.agency_name;
                    }
                    
                    // Close modal and redirect to staff list
                    agencySwitchModal.classList.add('hidden');
                    window.location.href = '/staff/';
                } else {
                    console.error('Failed to switch agency:', data.message);
                }
            } catch (error) {
                console.error('Error switching agency:', error);
            }
        });
    }

    function renderAgencyList(agencies, currentAgencyId) {
        if (!agencyList) return;

        agencyList.innerHTML = agencies.map(agency => `
            <div class="agency-item ${agency.id == currentAgencyId ? 'current' : ''}" data-agency-id="${agency.id}">
                <div>
                    <div class="agency-name">${agency.name}</div>
                    <div class="agency-status">${agency.id == currentAgencyId ? 'Current Agency' : 'Click to switch'}</div>
                </div>
            </div>
        `).join('');
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
                const response = await fetch(`/staff/api/profile/${profileId}/status`, {
                    method: 'POST',
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

    // Dispatch board: DnD + Create assignment modal
const lists = document.querySelectorAll(".dispatch-list");
if (lists.length && window.Sortable) {
  lists.forEach((list) => {
    new Sortable(list, {
      group: "dispatch",
      animation: 150,
      ghostClass: "sortable-ghost",
      dragClass: "sortable-drag",
      onEnd(evt) {
        const item = evt.item;
        const originalList = evt.from;
        const profileId = item?.dataset?.id;
        const newVenue = evt.to?.dataset?.venue;
        const staffName = item?.dataset?.name || "Staff";

        // Visually return the card to its original list immediately
        originalList.appendChild(item);

        if (!profileId || !newVenue) {
          return; // Abort if critical data is missing
        }

        if (newVenue === "available") {
          // Logic for de-assignment can be added here later
          alert("To de-assign staff, please manage their contract in the Payroll section.");
          return;
        }

        // If moved to a valid venue column, open the assignment modal
        if (typeof window.openAssignmentModal === "function") {
          window.openAssignmentModal(profileId, staffName, newVenue);
        } else {
          console.error("Assignment modal function not found.");
          alert("Error: Cannot open assignment modal.");
        }
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
    const positionInput = document.getElementById("assignmentRole"); // Keep same ID for compatibility
    const managerInput = document.getElementById("assignmentManager");

    async function populateAssignmentModalDropdowns() {
        try {
            const response = await fetch('/dispatch/api/assignment/form-data');
            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();

            if (data.status === 'success') {
                // Populate positions
                positionInput.innerHTML = '';
                data.positions.forEach(position => {
                    const option = new Option(position, position);
                    positionInput.add(option);
                });

                // Populate managers
                managerInput.innerHTML = '<option value="" disabled selected>-- Select a Manager --</option>';
                data.managers.forEach(manager => {
                    const option = new Option(manager.username, manager.id);
                    managerInput.add(option);
                });

                // Populate contracts
                contractTypeInput.innerHTML = '';
                data.contracts.forEach(contract => {
                    const option = new Option(contract.name, contract.name);
                    contractTypeInput.add(option);
                });
            } else {
                throw new Error(data.message || 'Failed to load form data');
            }
        } catch (error) {
            console.error("Error populating assignment modal:", error);
            alert("Could not load form data. Please check the console and try again.");
        }
    }

    async function openModal(staffId, staffName, venue) {
      if (!assignmentModal) return;

      staffNameSpan.textContent = staffName;
      venueInput.value = venue;
      positionInput.innerHTML = '<option>Loading...</option>';
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
        role: positionInput.value,
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
        const res = await fetch("/dispatch/api/assignment", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.message || "Server error");
        closeModal();
        window.location.href = '/payroll/';
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
             const penaltyRuleText = document.getElementById("penaltyRuleText");
            const DRINK_STAFF = 100;
            const DRINK_BAR = 220;
            const BAR_COMMISSION = DRINK_BAR - DRINK_STAFF; // 220 - 100 = 120 THB per drink
            const LATE_CUTOFF = "19:30";
            const TYPE_TO_DAYS = { '1day': 1, '10days': 10, '1month': 30 };
            const toTypeKey = (v) => String(v || '').trim().toLowerCase();
            
            // Contract rules will be loaded dynamically
            let currentContractRules = {
                late_cutoff_time: "19:30",
                first_minute_penalty: 0,
                additional_minute_penalty: 5
            };

                         function openPerformanceModal() { performanceModal?.classList.remove("hidden"); }
             function closePerformanceModal() { performanceModal?.classList.add("hidden"); }
             function openSummaryModal() { summaryModal?.classList.remove("hidden"); }
             function closeSummaryModal() { summaryModal?.classList.add("hidden"); }
             
             function updatePenaltyRuleText() {
                 if (penaltyRuleText) {
                     const firstMin = currentContractRules.first_minute_penalty;
                     const additionalMin = currentContractRules.additional_minute_penalty;
                     const cutoff = currentContractRules.late_cutoff_time;
                     
                     if (firstMin === 0) {
                         penaltyRuleText.textContent = `Late after ${cutoff} = ${additionalMin} THB/min from minute 1`;
                     } else {
                         penaltyRuleText.textContent = `Late after ${cutoff} = ${firstMin} THB first minute, then ${additionalMin} THB/min`;
                     }
                 }
             }

            closePerfBtn?.addEventListener("click", closePerformanceModal);
            cancelPerfBtn?.addEventListener("click", closePerformanceModal);
            closeSummaryBtn?.addEventListener("click", closeSummaryModal);

            function computePenalty(arrival) {
                if (!arrival) return 0;
                const cutoff = new Date(`1970-01-01T${currentContractRules.late_cutoff_time}:00`);
                const when = new Date(`1970-01-01T${arrival}:00`);
                if (when <= cutoff) return 0;
                const minutes = Math.round((when - cutoff) / 60000);
                
                console.log('Penalty calculation:', {
                    arrival,
                    cutoff: currentContractRules.late_cutoff_time,
                    minutes,
                    firstMinutePenalty: currentContractRules.first_minute_penalty,
                    additionalMinutePenalty: currentContractRules.additional_minute_penalty
                });
                
                if (minutes === 0) return 0;
                else if (minutes === 1) return currentContractRules.first_minute_penalty;
                else return currentContractRules.first_minute_penalty + (minutes - 1) * currentContractRules.additional_minute_penalty;
            }

            // ✅ NOUVEAU : Fonction pour récupérer et afficher le résumé final d'un contrat
            async function fetchAndShowFinalSummary(assignmentId) {
                try {
                    console.log(`Fetching final summary for assignment ${assignmentId}...`);
                    
                    const response = await fetch(`/payroll/api/summary/${assignmentId}`);
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.status !== 'success') {
                        throw new Error(data.message || 'Failed to fetch summary data');
                    }
                    
                    console.log('Final summary data received:', data);
                    
                    // ✅ TÂCHE 4 : Remplir la modale avec les données reçues
                    populateSummaryModal(data);
                    
                    // Afficher la modale
                    openSummaryModal();
                    
                } catch (error) {
                    console.error('Erreur lors de la récupération du résumé final:', error);
                    alert(`Erreur lors du chargement du résumé: ${error.message}`);
                }
            }
            
            // ✅ NOUVEAU : Fonction pour remplir la modale avec les données
            function populateSummaryModal(data) {
                // Récupérer les éléments de la modale
                const summaryStaffName = document.getElementById('summaryStaffName');
                const summaryAssignmentIdInput = document.getElementById('summaryAssignmentId');
                const summaryTotalDaysWorked = document.getElementById('summaryTotalDaysWorked');
                const summaryTotalDrinks = document.getElementById('summaryTotalDrinks');
                const summaryTotalSpecialComm = document.getElementById('summaryTotalSpecialComm');
                const summaryTotalCommission = document.getElementById('summaryTotalCommission');
                const summaryTotalSalary = document.getElementById('summaryTotalSalary');
                const summaryTotalProfit = document.getElementById('summaryTotalProfit');
                
                // Remplir les champs avec les données reçues
                if (summaryStaffName) summaryStaffName.textContent = data.staff_name || 'Unknown';
                if (summaryAssignmentIdInput) summaryAssignmentIdInput.value = data.assignment_id;
                if (summaryTotalDaysWorked) summaryTotalDaysWorked.textContent = `${data.total_days_worked || 0} days`;
                if (summaryTotalDrinks) summaryTotalDrinks.textContent = data.total_drinks_sold || 0;
                if (summaryTotalSpecialComm) summaryTotalSpecialComm.textContent = `${(data.total_special_commissions || 0).toFixed(0)}฿`;
                if (summaryTotalCommission) summaryTotalCommission.textContent = `${(data.total_commission_paid || 0).toFixed(0)}฿`;
                if (summaryTotalSalary) summaryTotalSalary.textContent = `${(data.total_salary_paid || 0).toFixed(0)}฿`;
                if (summaryTotalProfit) summaryTotalProfit.textContent = `${(data.total_profit || 0).toFixed(0)}฿`;
                
                // Appliquer les styles de couleur pour le profit
                if (summaryTotalProfit) {
                    summaryTotalProfit.classList.remove('profit-positive', 'profit-negative');
                    if (data.total_profit > 0) {
                        summaryTotalProfit.classList.add('profit-positive');
                    } else if (data.total_profit < 0) {
                        summaryTotalProfit.classList.add('profit-negative');
                    }
                }
            }

            // ✅ NOUVEAU : Fonction de prévisualisation avec debounce
            let previewDebounceTimer = null;
            
            async function previewPerformanceCalculation() {
                const assignmentId = assignmentIdInput.value;
                if (!assignmentId) return;
                
                // ✅ NOUVEAU : Indicateur visuel de chargement
                const summaryInputs = [latenessPenaltyInput, commissionPaidInput, proratedBaseInput, salaryPaidInput, barProfitInput];
                summaryInputs.forEach(input => {
                    if (input) {
                        input.style.backgroundColor = '#f0f8ff'; // Bleu clair pour indiquer le calcul
                        input.style.transition = 'background-color 0.3s ease';
                    }
                });
                
                // ✅ CORRIGÉ : Validation et formatage des données pour correspondre exactement à l'API
                const assignmentIdInt = parseInt(assignmentId, 10);
                if (isNaN(assignmentIdInt)) {
                    console.error('Invalid assignment ID:', assignmentId);
                    return;
                }
                
                const recordDate = recordDateInput.value;
                if (!recordDate) {
                    console.error('Record date is required');
                    return;
                }
                
                // Validation du format des heures (HH:MM)
                const validateTimeFormat = (timeStr) => {
                    if (!timeStr) return null;
                    const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/;
                    if (!timeRegex.test(timeStr)) {
                        console.warn('Invalid time format:', timeStr, 'Expected HH:MM');
                        return null;
                    }
                    return timeStr;
                };
                
                const payload = {
                    assignment_id: assignmentIdInt,
                    record_date: recordDate,
                    arrival_time: validateTimeFormat(arrivalInput.value),
                    departure_time: validateTimeFormat(departureInput.value),
                    drinks_sold: Math.max(0, parseInt(drinksInput.value || "0", 10)),
                    special_commissions: Math.max(0, parseFloat(specialInput.value || "0")),
                    bonus: parseFloat(bonusInput.value || "0"),
                    malus: parseFloat(malusInput.value || "0"),
                };
                
                // ✅ DEBUG : Afficher les données envoyées
                console.log('Sending preview data:', payload);
                
                try {
                    const response = await fetch("/payroll/api/performance/preview", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    // Mettre à jour le résumé avec les valeurs calculées
                    latenessPenaltyInput.value = (data.lateness_penalty || 0).toFixed(0);
                    commissionPaidInput.value = (data.commission_paid || 0).toFixed(0);
                    proratedBaseInput.value = (data.prorated_base || 0).toFixed(0);
                    salaryPaidInput.value = (data.daily_salary || 0).toFixed(0);
                    barProfitInput.value = (data.daily_profit || 0).toFixed(0);
                    
                    // ✅ NOUVEAU : Retour à la couleur normale
                    summaryInputs.forEach(input => {
                        if (input) {
                            input.style.backgroundColor = '';
                        }
                    });
                    
                    console.log('Preview calculation updated:', data);
                    
                } catch (error) {
                    console.error('Erreur lors de la prévisualisation:', error);
                    
                    // ✅ AMÉLIORÉ : Messages d'erreur plus informatifs
                    if (error.message.includes('HTTP error! status: 400')) {
                        console.error('Données invalides envoyées à l\'API. Vérifiez les valeurs saisies.');
                    } else if (error.message.includes('HTTP error! status: 500')) {
                        console.error('Erreur serveur lors du calcul. Contactez l\'administrateur.');
                    }
                    
                    // ✅ NOUVEAU : Retour à la couleur normale même en cas d'erreur
                    summaryInputs.forEach(input => {
                        if (input) {
                            input.style.backgroundColor = '';
                        }
                    });
                }
            }
            
            function debouncedPreview() {
                // Annuler le timer précédent
                if (previewDebounceTimer) {
                    clearTimeout(previewDebounceTimer);
                }
                
                // Créer un nouveau timer de 300ms
                previewDebounceTimer = setTimeout(() => {
                    previewPerformanceCalculation();
                }, 300);
            }
            
            // ✅ NOUVEAU : Attacher la prévisualisation à tous les champs pertinents
            const previewFields = [arrivalInput, departureInput, drinksInput, specialInput, bonusInput, malusInput];
            previewFields.forEach(field => {
                if (field) {
                    field.addEventListener("input", debouncedPreview);
                }
            });
            
            // ✅ CORRIGÉ : Fonction de calcul de pénalité en temps réel (pour l'arrival time uniquement)
            function recomputeDailySummary() {
                const penalty = computePenalty(arrivalInput.value);
                latenessPenaltyInput.value = penalty.toFixed(0);
            }
            
            // ✅ CORRIGÉ : Seul l'arrival time peut affecter la pénalité en temps réel
            arrivalInput?.addEventListener("input", recomputeDailySummary);

            async function loadRecord(assignmentId, ymd) {
                try {
                    const res = await fetch(`/payroll/api/performance/${assignmentId}/${ymd}`);
                    const data = await res.json();
                    if (data && data.record) {
                        const r = data.record;
                        // ✅ CORRIGÉ : Utiliser les données du PerformanceRecord
                        arrivalInput.value = r.arrival_time || "";
                        departureInput.value = r.departure_time || "";
                        drinksInput.value = r.drinks_sold ?? 0;
                        specialInput.value = r.special_commissions ?? 0;
                        bonusInput.value = r.bonus ?? 0;
                        malusInput.value = r.malus ?? 0;
                        
                        // ✅ NOUVEAU : Utiliser les valeurs calculées par le serveur
                        latenessPenaltyInput.value = (r.lateness_penalty || 0).toFixed(0);
                        commissionPaidInput.value = (r.drinks_sold * DRINK_STAFF || 0).toFixed(0);
                        proratedBaseInput.value = (r.daily_salary - r.bonus + r.malus + r.lateness_penalty || 0).toFixed(0);
                        salaryPaidInput.value = (r.daily_salary || 0).toFixed(0);
                        barProfitInput.value = (r.daily_profit || 0).toFixed(0);
                    } else {
                        // Nouveau record - vider tous les champs
                        [arrivalInput, departureInput].forEach(i => i.value = "");
                        [drinksInput, specialInput, bonusInput, malusInput].forEach(i => i.value = 0);
                        [latenessPenaltyInput, commissionPaidInput, proratedBaseInput, salaryPaidInput, barProfitInput].forEach(i => i.value = "0");
                        
                        // ✅ NOUVEAU : Déclencher la prévisualisation pour un nouveau record
                        setTimeout(() => previewPerformanceCalculation(), 100);
                    }
                } catch (e) {
                    console.error("loadRecord error", e);
                }
            }
            
            async function loadPerformanceHistory(assignmentId) {
                try {
                    historyBox.innerHTML = "";
                    const res = await fetch(`/payroll/api/performance/${assignmentId}`);
                    const data = await res.json();
                    if (!data || !data.records || !data.contract) {
                        historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load contract data.</p>`;
                        return;
                    }
                                         const list = data.records;
                     const contract = data.contract;
                     
                     // Update current contract rules
                     if (contract.contract_rules) {
                         currentContractRules = contract.contract_rules;
                         updatePenaltyRuleText();
                     }
                     
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
                            // ✅ CORRIGÉ : Utiliser les valeurs calculées par le serveur depuis PerformanceRecord
                            const commission = (r.drinks_sold || 0) * DRINK_STAFF;
                            const salary = r.daily_salary || 0;
                            const profit = r.daily_profit || 0;
                            tr.innerHTML = `<td>${new Date(r.record_date + 'T00:00:00').toLocaleDateString('en-GB', {day:'2-digit', month:'2-digit'})}</td><td>${r.drinks_sold || 0}</td><td>${(r.special_commissions || 0).toFixed(0)}฿</td><td>${salary.toFixed(0)}฿</td><td>${commission.toFixed(0)}฿</td><td>${profit.toFixed(0)}฿</td>`;
                            tr.addEventListener("click", () => { recordDateInput.value = r.record_date; loadRecord(assignmentId, r.record_date); });
                            tbody.appendChild(tr);
                        });
                        historyBox.appendChild(tableEl);
                    }

                    // --- LOGIC CORRECTION ---
                    // Show summary if the contract is finished, regardless of days worked.
                    if (contract.status === 'completed' || contract.status === 'archived') {
                        calculateAndShowSummary(assignmentId, list, contract, baseDaily);
                    }

                } catch (e) {
                    console.error(e);
                    historyBox.innerHTML = `<p class="text-center" style="padding:.5rem;">Could not load history.</p>`;
                }
            }
            
            async function calculateAndShowSummary(assignmentId, records, contract, baseDaily) {
                try {
                    // Appeler l'endpoint API pour récupérer les données calculées
                    const response = await fetch(`/payroll/api/assignment/${assignmentId}/summary`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    // Récupérer le nom du staff depuis le DOM
                    const row = document.getElementById(`assignment-row-${assignmentId}`);
                    if (!row) {
                        console.error(`Row not found for assignment ${assignmentId}`);
                        return;
                    }
                    
                    // Utiliser les données JSON reçues pour remplir les totaux
                    summaryAssignmentIdInput.value = assignmentId;
                    summaryStaffName.textContent = modalStaffName.textContent;
                    summaryTotalDaysWorked.textContent = `${data.days_worked || 0} days`;
                    summaryTotalDrinks.textContent = data.total_drinks || 0;
                    summaryTotalSpecialComm.textContent = `${(data.total_special_comm || 0).toFixed(0)}฿`;
                    summaryTotalCommission.textContent = `${(data.total_commission || 0).toFixed(0)}฿`;
                    summaryTotalSalary.textContent = `${(data.total_salary || 0).toFixed(0)}฿`;
                    summaryTotalProfit.textContent = `${(data.total_profit || 0).toFixed(0)}฿`;
                    
                    const profitEl = summaryTotalProfit;
                    profitEl.classList.remove('profit-positive', 'profit-negative');
                    if (data.total_profit > 0) profitEl.classList.add('profit-positive');
                    else if (data.total_profit < 0) profitEl.classList.add('profit-negative');
                    
                    openSummaryModal();
                    
                } catch (error) {
                    console.error('Erreur lors de la récupération du résumé:', error);
                    alert('Erreur lors du chargement du résumé du contrat. Veuillez réessayer.');
                }
            }

            async function finalizeContract(assignmentId, status) {
                const row = document.getElementById(`assignment-row-${assignmentId}`);
                const name = row ? (row.dataset.staffName || 'this contract') : 'this contract';
                if (!confirm(`This will finalize the contract for "${name}" as ${status}. Continue?`)) return;
                try {
                    const res = await fetch(`/dispatch/api/assignment/${assignmentId}/finalize`, {
                        method: 'POST',
                        body: JSON.stringify({ status: status })
                    });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data.message || "Server error");
                    closeSummaryModal();
                    closePerformanceModal();
                    if (row) {
                        row.classList.remove('status-active');
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
                    const pdfUrl = `/payroll/assignment/${assignmentId}/pdf`;
                    window.open(pdfUrl, '_blank');
                } else {
                    alert('Error: Could not determine the Assignment ID.');
                }
            });

            table.addEventListener("click", async (e) => {
                // Sélecteur robuste avec plusieurs fallbacks
                let tr = e.target.closest("tr[id^='assignment-row-']");
                if (!tr) {
                    // Fallback 1: essayer avec data-assignment-id
                    tr = e.target.closest("tr[data-assignment-id]");
                }
                if (!tr) {
                    // Fallback 2: essayer de trouver la ligne parente par classe
                    tr = e.target.closest("tr.status-active, tr.status-ended, tr.status-archived");
                }
                if (!tr) {
                    console.warn("Impossible de trouver la ligne de contrat pour l'élément cliqué:", e.target);
                    return;
                }
                const assignmentId = tr.dataset.assignmentId;
                const staffName = tr.dataset.staffName;
                
                // Vérification des données requises
                if (!assignmentId) {
                    console.error("ID d'assignation manquant dans la ligne:", tr);
                    return;
                }

                if (e.target.closest(".manage-performance-btn")) {
                    const startIso = tr.dataset.startDate, endIso = tr.dataset.endDate;
                    assignmentIdInput.value = assignmentId;
                    contractDaysInput.value = String(tr.dataset.contractDays || "1");
                    contractBaseSalaryInput.value = String(tr.dataset.baseSalary || "0");
                    contractStartInput.value = startIso;
                    contractEndInput.value = endIso;
                    modalStaffName.textContent = staffName || "";
                    const cType = (tr.dataset.contractType || "").trim();
                    // Use the contract name directly since it's now stored as the contract name
                    modalContractBadge.textContent = cType;
                    // Generate a CSS class based on the contract name for styling
                    const badgeClass = "contract-badge badge-" + cType.toLowerCase().replace(/\s+/g, '-');
                    modalContractBadge.className = badgeClass;
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

                // ✅ NOUVEAU : Gestion du bouton "Details" pour les contrats terminés
                if (e.target.matches('.btn-details')) {
                    const contractStatus = tr.dataset.currentStatus || tr.className.match(/status-(\w+)/)?.[1];
                    
                    // Vérifier si le contrat est terminé (ended ou archived)
                    if (contractStatus === 'ended' || contractStatus === 'archived') {
                        console.log(`Opening final summary for ${contractStatus} contract ${assignmentId}`);
                        await fetchAndShowFinalSummary(assignmentId);
                        return;
                    }
                }

                if (e.target.closest(".end-contract-btn")) {
                    if (!confirm(`This will end the contract for "${staffName}" today and open the final summary. Continue?`)) return;
                    try {
                        const res = await fetch(`/dispatch/api/assignment/${assignmentId}/end`, { method: "POST" });
                        const data = await res.json().catch(() => ({}));
                        if (!res.ok) throw new Error(data.message || "Server error");
                        location.reload();
                    } catch (err) {
                        alert(err.message || "Network error");
                    }
                    return;
                }

                if (e.target.closest(".archive-contract-btn")) {
                    if (!confirm(`Archive this contract for "${staffName}"? This will mark it as permanently archived.`)) return;
                    try {
                        const res = await fetch(`/dispatch/api/assignment/${assignmentId}/archive`, { method: "POST" });
                        const data = await res.json().catch(() => ({}));
                        if (!res.ok) throw new Error(data.message || "Server error");
                        alert("Contract archived successfully");
                        window.location.reload(); // Refresh to show updated status
                    } catch (err) {
                        alert(err.message || "Network error");
                    }
                    return;
                }

                if (e.target.closest(".delete-contract-btn")) {
                    if (!confirm(`Delete this contract for "${staffName}"? This cannot be undone.`)) return;
                    try {
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
                    const res = await fetch("/payroll/api/performance", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data.message || "Server error");
                    alert("Saved successfully");
                    await loadRecord(payload.assignment_id, payload.record_date);
                    await loadPerformanceHistory(payload.assignment_id);
                    
                    // Refresh the payroll page to update progress bars
                    if (window.location.pathname === '/payroll/') {
                        window.location.reload();
                    }
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
    // Only handle delete buttons on staff-related pages
    if (!location.pathname.includes('/staff/') && !location.pathname.includes('/payroll/')) {
      return;
    }
    
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