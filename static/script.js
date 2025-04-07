document.addEventListener("DOMContentLoaded", function () {
    const sendEmailButton = document.getElementById("send-email");

    if (sendEmailButton) {
        sendEmailButton.addEventListener("click", function () {
            const emailBodyElement = document.getElementById("email-body");
            if (!emailBodyElement) {
                alert("Email content not found!");
                return;
            }

            const emailBody = emailBodyElement.value.trim();
            if (emailBody === "") {
                alert("Email content is empty!");
                return;
            }

            const subject = encodeURIComponent("Interview Evaluation Results");
            const body = encodeURIComponent(emailBody);
            const toEmail = "seetureddy26@gmail.com";  // <-- Change this to your default email
            const mailtoLink = `https://mail.google.com/mail/?view=cm&fs=1&tf=1&to=${toEmail}&su=${subject}&body=${body}`;

            window.open(mailtoLink, "_blank");
        });
    }
});
