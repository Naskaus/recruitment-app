document.addEventListener('DOMContentLoaded', function() {
    
    // --- Logic for the Profile Creation/Edit Form ---
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        const photoInput = document.getElementById('photo');
        const photoPreview = document.getElementById('photoPreview');
        const photoPlaceholder = document.getElementById('photoPlaceholder');
        const submitButton = profileForm.querySelector('button[type="submit"]');

        if (photoInput && photoPreview && photoPlaceholder) {
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
                formResponseDiv.classList.remove('hidden', 'success');
                formResponseDiv.textContent = 'A network error occurred. Please try again.';
                formResponseDiv.classList.add('error');
                submitButton.disabled = false;
                submitButton.textContent = mode === 'edit' ? 'Update Profile' : 'Create Profile';
            });
        });
    }

    // --- Logic for the Staff List Page ---
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
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
    }
    
    // --- Logic for Deleting a Profile (from Detail Page or Card) ---
    document.addEventListener('click', function(e) {
        const deleteButton = e.target.closest('.button.button-danger, .card-delete-button');
        if (deleteButton) {
            e.preventDefault();
            const profileId = deleteButton.dataset.id;
            const profileName = deleteButton.dataset.name;
            handleDelete(profileId, profileName);
        }
    });

});

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