//timeline
const tl = gsap.timeline({ defaults: { ease: "power1.out" } });

//stagger = väli millä eri objectit alkaa animoimaan toisistaan
tl.to(".text", { y: "0%", duration: 0.7, stagger: 0.25 });

//ku käytämmy tl.xxx  vs  gsap.xxx niin timelinessa eka animaatio menee loppuun ennenku seuraava alkaa
tl.to(".slider", { y: "-100%", duration: 1, delay: 0.5 });

//push the darkness harmaan sliderin kanssa ylös piiloon
//-=1  tarkoittaa, että aloita sekunttia aikaisemmin, jotta se menee samaan syssyyn ku toi harmaa nostopalkki
tl.to(".intro", { y: "-100%", duration: 1 }, "-=1");

//ottaa esiin smoothisti
tl.fromTo('nav', {opacity: 0}, {opacity: 1, duration: 1});
tl.fromTo('.big-text', {opacity: 0}, {opacity: 1, duration: 1}, "-=1");