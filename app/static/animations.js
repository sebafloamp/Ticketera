document.addEventListener("DOMContentLoaded", function () {
    var fadeEls = document.querySelectorAll(".fade-up");
    var fadeIo = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("in");
                    fadeIo.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12 }
    );
    fadeEls.forEach(function (el) { fadeIo.observe(el); });

    var bars = document.querySelectorAll(".bar-fill[data-target]");
    var barIo = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.style.width = entry.target.getAttribute("data-target") + "%";
                    barIo.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.3 }
    );
    bars.forEach(function (el) { barIo.observe(el); });
});
