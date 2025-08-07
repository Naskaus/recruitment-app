document.addEventListener('DOMContentLoaded', function() {
    
    // --- Logic for the Profile Creation Form ---
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        // Photo Preview Handler
        const photoInput = document.getElementById('photo');
        const photoPreview = document.getElementById('photoPreview');

        if (photoInput && photoPreview) {
            photoInput.addEventListener('change', function(event) {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        photoPreview.src = e.target.result;
                    }
                    reader.readAsDataURL(file);
                }
            });
        }

        // Form Submission Handler
        profileForm.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission

            const formData = new FormData(profileForm);
            const formResponseDiv = document.getElementById('form-response');

            fetch('/api/profile', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
                formResponseDiv.textContent = data.message || 'Profile created successfully!';
                formResponseDiv.className = 'success';
                formResponseDiv.classList.remove('hidden');
                profileForm.reset();
                photoPreview.src = 'https://via.placeholder.com/150';

                // Optional: Redirect to the staff list after a short delay
                setTimeout(() => {
                    window.location.href = '/staff';
                }, 1500);
            })
            .catch((error) => {
                console.error('Error:', error);
                formResponseDiv.textContent = 'An error occurred. Please try again.';
                formResponseDiv.className = 'error';
                formResponseDiv.classList.remove('hidden');
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
                // Use 'flex' as it's the display type set in CSS for the card
                if (selectedStatus === 'all' || card.dataset.status === selectedStatus) {
                    card.style.display = 'flex'; 
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }
});