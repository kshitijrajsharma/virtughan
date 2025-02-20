// Function to show message boxes
function showMessage(type, message) {
    var messageBoxes = document.getElementById('message-boxes');
    var successMessage = document.getElementById('success-message');
    var warningMessage = document.getElementById('warning-message');
    var messageContent = document.getElementById('message-cont');
    var warningContent = document.getElementById('warning-cont');

    messageBoxes.classList.remove('hidden');
    messageBoxes.classList.add('z-50'); // Set higher z-index using Tailwind

    if (type === 'success') {
        successMessage.classList.remove('hidden');
        messageContent.innerHTML = message;
        warningMessage.classList.add('hidden');
    } else if (type === 'warning' || type === 'error') {
        successMessage.classList.add('hidden');
        warningContent.innerHTML = message;
        warningMessage.classList.remove('hidden');
    }

    if(type != 'error'){
        setTimeout(function() {
            hideMessage();
        }, 10000); // automatically close after certain seconds
    }
}

// Function to hide message boxes
function hideMessage() {
    var messageBoxes = document.getElementById('message-boxes');
    messageBoxes.classList.add('hidden');
    messageBoxes.classList.remove('z-50'); // Reset to default z-index using Tailwind
}

// Add event listeners to close buttons
document.querySelectorAll('.close-button-message').forEach(button => {
    button.addEventListener('click', hideMessage);
});

