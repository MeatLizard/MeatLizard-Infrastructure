// server/web/app/static/js/video_player.js
const player = videojs('my-video', {
    playbackRates: [0.5, 1, 1.5, 2],
    controls: true,
    autoplay: false,
    preload: 'auto',
    fluid: true,
});

const themeToggleButton = document.getElementById('theme-toggle');
themeToggleButton.addEventListener('click', () => {
    player.toggleClass('light-mode');
});
