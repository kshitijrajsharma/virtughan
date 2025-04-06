// Function to show message boxes
function showMessage(type, time, message) {
    var messageBoxes = document.getElementById('message-boxes');
    var successMessage = document.getElementById('success-message');
    var warningMessage = document.getElementById('warning-message');
    var messageContent = document.getElementById('message-cont');
    var warningContent = document.getElementById('warning-cont');

    messageBoxes.classList.remove('hidden');
    messageBoxes.classList.add('z-50'); // Set higher z-index using Tailwind

    if (type === 'success' || type === 'message') {
        successMessage.classList.remove('hidden');
        messageContent.innerHTML = message;
        warningMessage.classList.add('hidden');
    } else if (type === 'warning' || type === 'error') {
        successMessage.classList.add('hidden');
        warningContent.innerHTML = message;
        warningMessage.classList.remove('hidden');
    }

    if(type != 'error'){
        document.getElementById('warning_error').innerText = 'Warning!';
        setTimeout(function() {
            hideMessage();
        }, time); // automatically close after certain seconds
    }
    else{
        document.getElementById('warning_error').innerText = 'Error!';
    }

    if(type == 'message'){
        document.getElementById('success_and_message').innerText = 'Info!'; 
        document.getElementById('success-message').classList.remove("bg-green-100");
        document.getElementById('success-message').classList.remove("border-green-400");
        document.getElementById('success-message').classList.remove("text-green-700");

        document.getElementById('success-message').classList.add("bg-gray-50");
        document.getElementById('success-message').classList.add("border-gray-400");
        document.getElementById('success-message').classList.add("text-gray-700");
    }
    else if(type == 'success'){
        document.getElementById('success_and_message').innerText = 'Success!';

        document.getElementById('success-message').classList.remove("bg-gray-50");
        document.getElementById('success-message').classList.remove("border-gray-400");
        document.getElementById('success-message').classList.remove("text-gray-700");

        document.getElementById('success-message').classList.add("bg-green-100");
        document.getElementById('success-message').classList.add("border-green-400");
        document.getElementById('success-message').classList.add("text-green-700");

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

