document.addEventListener('DOMContentLoaded', function() {
    
    // --- Photo Preview Handler ---
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

    // --- Form Submission Handler ---
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
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
                formResponseDiv.className = 'success'; // Add success class for styling
                profileForm.reset(); // Reset form fields
                photoPreview.src = 'https://via.placeholder.com/150'; // Reset preview image
            })
            .catch((error) => {
                console.error('Error:', error);
                formResponseDiv.textContent = 'An error occurred. Please try again.';
                formResponseDiv.className = 'error'; // Add error class for styling
            });
        });
    }
});