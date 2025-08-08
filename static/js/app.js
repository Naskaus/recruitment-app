document.addEventListener('DOMContentLoaded', function() {
    
    // --- General Helper Functions ---
    const showToast = (message, type = 'error') => {
        console.error(`Error: ${message}`);
        alert(message);
    };

    // --- Logic for the Profile Creation/Edit Form ---
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        // This logic remains unchanged
        const photoInput = document.getElementById('photo');
        const photoPreview = document.getElementById('photoPreview');
        const photoPlaceholder = document.getElementById('photoPlaceholder');
        if (photoInput) {
            photoInput.addEventListener('change', function(event) {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        photoPreview.src = e.target.result;
                        photoPreview.classList.remove('hidden');
                        photoPlaceholder.classList.add('hidden');
                    }
                    reader.readAsDataURL(file);
                }
            });
        }
        profileForm.addEventListener('submit', function(event) {
            event.preventDefault();
            const submitButton = profileForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Saving...';
            const formData = new FormData(profileForm);
            const formResponseDiv = document.getElementById('form-response');
            
            const mode = profileForm.dataset.mode;
            const profileId = profileForm.dataset.id;
            
            let url = '/api/profile';
            if (mode === 'edit') {
                url = `/api/profile/${profileId}`;
            }

            fetch(url, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                formResponseDiv.classList.remove('hidden', 'success', 'error');
                if (data.status === 'success') {
                    formResponseDiv.textContent = data.message;
                    formResponseDiv.classList.add('success');
                    setTimeout(() => {
                        if (mode === 'edit') {
                            window.location.href = `/profile/${profileId}`;
                        } else {
                            window.location.href = '/staff';
                        }
                    }, 1500);
                } else {
                    formResponseDiv.textContent = data.message || 'An error occurred.';
                    formResponseDiv.classList.add('error');
                    submitButton.disabled = false;
                    submitButton.textContent = mode === 'edit' ? 'Update Profile' : 'Create Profile';
                }
            })
            .catch((error) => {
                console.error('Error:', error);
                showToast('A network error occurred. Please try again.');
                submitButton.disabled = false;
                submitButton.textContent = mode === 'edit' ? 'Update Profile' : 'Create Profile';
            });
        });
    }

    // --- Logic for the Staff List Page ---
    const staffGrid = document.querySelector('.staff-grid');
    if (staffGrid) {
        const statusFilter = document.getElementById('statusFilter');
        statusFilter.addEventListener('change', function() {
            const selectedStatus = this.value;
            const staffCards = document.querySelectorAll('.staff-card');
            staffCards.forEach(function(card) {
                if (selectedStatus === 'all' || card.dataset.status === selectedStatus) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });

        new Sortable(staffGrid, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
        });
    }
    
    // --- Dispatch Board Logic ---
    const dispatchLists = document.querySelectorAll('.dispatch-list');
    if (dispatchLists.length > 0) {
        dispatchLists.forEach(list => {
            new Sortable(list, {
                group: 'dispatch',
                animation: 150,
                ghostClass: 'dispatch-card-ghost',
                dragClass: 'dispatch-card-drag',
                onEnd: function (evt) {
                    const profileId = evt.item.dataset.id;
                    const newVenue = evt.to.dataset.venue;
                    updateStaffVenue(profileId, newVenue);
                },
            });
        });
    }

    // --- Payroll Page & Modal Logic ---
    const payrollPage = document.querySelector('.payroll-table');
    if (payrollPage) {
        const modal = document.getElementById('editRecordModal');
        const form = document.getElementById('editRecordForm');
        const closeModalBtn = document.getElementById('closeModalBtn');
        const cancelModalBtn = document.getElementById('cancelModalBtn');
        const submitBtn = form.querySelector('button[type="submit"]');

        const modalStaffName = document.getElementById('modalStaffName');
        const modalRecordDate = document.getElementById('modalRecordDate');
        const recordIdInput = document.getElementById('recordId');
        const arrivalInput = document.getElementById('arrivalTime');
        const departureInput = document.getElementById('departureTime');
        const drinksInput = document.getElementById('drinksSold');
        const specialInput = document.getElementById('specialCommissions');
        const salaryInput = document.getElementById('dailySalary');
        const otherInput = document.getElementById('otherDeductions');

        const latenessPenaltyInput = document.getElementById('latenessPenalty');
        const drinkCommissionsInput = document.getElementById('drinkCommissions');
        const staffNetPayInput = document.getElementById('staffNetPay');
        const agencyNetProfitInput = document.getElementById('agencyNetProfit');
        
        const historyContainer = document.getElementById('recordHistory');

        const STANDARD_ARRIVAL_TIME = "19:00";

        const calculatePerformance = () => {
            const drinksSold = parseFloat(drinksInput.value) || 0;
            const specialCommissions = parseFloat(specialInput.value) || 0;
            const dailySalary = parseFloat(salaryInput.value) || 0;
            const otherDeductions = parseFloat(otherInput.value) || 0;
            const arrivalTime = arrivalInput.value;

            // Lateness Penalty
            let latenessPenalty = 0;
            if (arrivalTime) {
                const standardDate = new Date(`1970-01-01T${STANDARD_ARRIVAL_TIME}:00`);
                const arrivalDate = new Date(`1970-01-01T${arrivalTime}:00`);
                if (arrivalDate > standardDate) {
                    const minutesLate = (arrivalDate - standardDate) / 60000;
                    latenessPenalty = 100 + (minutesLate * 5);
                }
            }
            latenessPenaltyInput.value = latenessPenalty.toFixed(2);

            // Drink Commission
            const drinkCommission = drinksSold * 100;
            drinkCommissionsInput.value = drinkCommission.toFixed(2);
            
            // Staff Net Pay (Base + Commissions + Bonus/Deduction - Penalty)
            const staffNetPay = dailySalary + drinkCommission + otherDeductions - latenessPenalty;
            staffNetPayInput.value = staffNetPay.toFixed(2);

            // Agency Profit (Drinks Revenue + Special Sales - Base Salary Paid)
            const agencyRevenueFromDrinks = drinksSold * 120;
            const agencyProfit = (agencyRevenueFromDrinks + specialCommissions) - dailySalary;
            agencyNetProfitInput.value = agencyProfit.toFixed(2);
        };

        const renderHistory = (history) => {
            historyContainer.innerHTML = '';
            if (!history || history.length === 0) {
                historyContainer.innerHTML = '<p class="text-center" style="padding: 1rem;">No recent history found.</p>';
                return;
            }
            history.forEach(rec => {
                const historyItem = createHistoryElement(rec);
                historyContainer.appendChild(historyItem);
            });
        };

        const createHistoryElement = (rec) => {
            const item = document.createElement('div');
            item.className = 'history-item';
            const date = new Date(rec.record_date + 'T00:00:00');
            const formattedDate = date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
            
            const drinkComm = (rec.drinks_sold || 0) * 100;
            const netPay = (rec.daily_salary || 0) + drinkComm + (rec.other_deductions || 0) - (rec.lateness_penalty || 0);

            item.innerHTML = `
                <div><span>Date:</span> <strong>${formattedDate}</strong></div>
                <div><span>Drinks:</span> <strong>${rec.drinks_sold}</strong></div>
                <div><span>Penalty:</span> <strong>${(rec.lateness_penalty || 0).toFixed(0)} THB</strong></div>
                <div><span>Net Pay:</span> <strong>${netPay.toFixed(0)} THB</strong></div>
            `;
            return item;
        };

        const openModal = () => modal.classList.remove('hidden');
        const closeModal = () => modal.classList.add('hidden');

        const populateForm = (data) => {
            const { record, history } = data;
            
            const recordDate = new Date(record.record_date + 'T00:00:00');
            modalRecordDate.textContent = recordDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });

            recordIdInput.value = record.id;
            arrivalInput.value = record.arrival_time || '';
            departureInput.value = record.departure_time || '';
            drinksInput.value = record.drinks_sold || 0;
            specialInput.value = record.special_commissions || 0;
            salaryInput.value = record.daily_salary || 800;
            otherInput.value = record.other_deductions || 0;
            
            calculatePerformance();
            renderHistory(history);
        };

        payrollPage.addEventListener('click', async (e) => {
            const button = e.target.closest('button');
            if (!button) return;

            if (button.matches('.add-record-btn')) {
                const staffId = button.dataset.id;
                button.disabled = true;
                button.textContent = 'Creating...';
                try {
                    const response = await fetch('/api/performance-record/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ staff_id: staffId }),
                    });
                    if (response.ok) window.location.reload();
                    else {
                        const data = await response.json();
                        showToast(data.message || 'Error creating record.');
                        button.disabled = false;
                        button.textContent = 'Add Daily Record';
                    }
                } catch (error) {
                    showToast('Network error. Could not create record.');
                    button.disabled = false;
                    button.textContent = 'Add Daily Record';
                }
            }

            if (button.matches('.edit-record-btn')) {
                const recordId = button.dataset.recordId;
                const staffName = button.dataset.staffName;
                modalStaffName.textContent = staffName;
                try {
                    const response = await fetch(`/api/performance-record/${recordId}`);
                    const data = await response.json();
                    if (response.ok) {
                        populateForm(data);
                        openModal();
                    } else {
                        showToast(data.message || 'Could not fetch record data.');
                    }
                } catch (error) {
                    showToast('Network error. Could not fetch record data.');
                }
            }
        });

        closeModalBtn.addEventListener('click', closeModal);
        cancelModalBtn.addEventListener('click', closeModal);
        form.addEventListener('input', calculatePerformance);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';

            const recordId = recordIdInput.value;
            const formData = {
                arrival_time: arrivalInput.value || null,
                departure_time: departureInput.value || null,
                drinks_sold: drinksInput.value,
                special_commissions: specialInput.value,
                daily_salary: salaryInput.value,
                other_deductions: otherInput.value,
                lateness_penalty: latenessPenaltyInput.value,
            };

            try {
                const response = await fetch(`/api/performance-record/${recordId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData),
                });
                const data = await response.json();
                if (response.ok) {
                    // Create and animate the new history item for visual feedback
                    const newHistoryItem = createHistoryElement(data.record);
                    newHistoryItem.classList.add('new-item');
                    
                    const placeholder = historyContainer.querySelector('p');
                    if(placeholder) placeholder.remove();
                    historyContainer.prepend(newHistoryItem);

                    // Wait for the animation to be visible, then close and reload for data consistency
                    setTimeout(() => {
                        closeModal();
                        window.location.reload();
                    }, 1500);
                } else {
                    showToast(data.message || 'Failed to save the record.');
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Save Changes';
                }
            } catch (error) {
                showToast('Network error. Could not save the record.');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Save Changes';
            }
        });
    }

    // --- Global Click Listener for Deletes ---
    document.addEventListener('click', function(e) {
        const deleteButton = e.target.closest('.button-danger, .card-delete-button');
        if (deleteButton) {
            e.preventDefault();
            const profileId = deleteButton.dataset.id;
            const profileName = deleteButton.dataset.name;
            handleDelete(profileId, profileName);
        }
    });

});

// --- Globally Scoped Helper Functions ---
function handleDelete(profileId, profileName) {
    if (confirm(`Are you sure you want to permanently delete the profile for "${profileName}"? This action cannot be undone.`)) {
        fetch(`/api/profile/${profileId}/delete`, {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                if (window.location.pathname.includes(`/profile/${profileId}`)) {
                    window.location.href = '/staff';
                } else {
                    const cardToRemove = document.querySelector(`.staff-card[data-id='${profileId}']`);
                    if (cardToRemove) {
                        cardToRemove.style.transition = 'opacity 0.5s ease';
                        cardToRemove.style.opacity = '0';
                        setTimeout(() => cardToRemove.remove(), 500);
                    }
                }
            } else {
                alert('Error deleting profile: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('A network error occurred while trying to delete the profile.');
        });
    }
}

function updateStaffVenue(profileId, newVenue) {
    fetch(`/api/profile/${profileId}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ venue: newVenue }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log(data.message);
            // Update staff count on the UI
            document.querySelectorAll('.dispatch-column-header').forEach(header => {
                const list = header.nextElementSibling;
                const countSpan = header.querySelector('.staff-count');
                if(list && countSpan) {
                    countSpan.textContent = list.children.length;
                }
            });
        } else {
            console.error('Failed to update venue:', data.message);
            alert('Error updating assignment. Please refresh the page.');
        }
    })
    .catch(error => {
        console.error('Network error:', error);
        alert('Network error. Please check your connection and refresh the page.');
    });
}
