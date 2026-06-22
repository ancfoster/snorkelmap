const burgerMenuButton = document.querySelector('.hamburger');
const mobileNavWrapper = document.querySelector('.mobile-nav__wrapper');

// Open and close mobile menu
burgerMenuButton.addEventListener('click', () => {
    mobileNavWrapper.classList.toggle('hidden');
    burgerMenuButton.classList.toggle('is-active');
})

// If mobile menu is open and resized on desktop, close mobile nav menu at same viewport width where burger menu icon disappears
window.addEventListener('resize', () => {
    const vpw = window.innerWidth;
    if (vpw > 870) {
        mobileNavWrapper.classList.add('hidden');
        burgerMenuButton.classList.remove('is-active');
    }
})