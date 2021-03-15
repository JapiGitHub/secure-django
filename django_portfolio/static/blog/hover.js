console.log("initializing 3d logos ... ")
//3d moving animation logos

//variables
const collisionBox = document.querySelector('.collisionBox');
const baseCard = document.querySelector('.baseCard');
const logo = document.querySelector('.plate img');
const circle = document.querySelector('.circle');
const title = document.querySelector('.info h1');
const info = document.querySelector('.info h3');
const button = document.querySelector('#likeButton')
const button2 = document.querySelector('#likeButton2')


const collisionBox2 = document.querySelector('.collisionBox2');
const baseCard2 = document.querySelector('.baseCard2');
const logo2 = document.querySelector('.plate2 img');
const circle2 = document.querySelector('.circle2');
const title2 = document.querySelector('.info2 h1');
const info2 = document.querySelector('.info2 h3');


button.addEventListener("click", (e) => {
button.style.background='#6efdfd';
});

button2.addEventListener("click", (e) => {
button2.style.background='#c3082a';
});


//mousemove = hover
collisionBox.addEventListener("mousemove", (e) => {
// kahdella jakaminen pääsee screenin keskelle
let xAx = ((window.innerWidth / 100)*35 - e.pageX) / 12;
let yAx = (window.innerHeight / 1.6 - e.pageY) / 12;

baseCard.style.transform = `rotateY(${xAx}deg) rotateX(${yAx}deg)`;

});

collisionBox2.addEventListener("mousemove", (e) => {
// kahdella jakaminen pääsee screenin keskelle
let xAx = ((window.innerWidth / 100)*63 - e.pageX) / 15;
let yAx = (window.innerHeight / 1.8 - e.pageY) / 15;

baseCard2.style.transform = `rotateY(${xAx}deg) rotateX(${yAx}deg)`;

});



//liikkeen aloitus. ottaa hitaasti paikalleen palaamisen pois päältä jotta se ei vaikuta hoverissa
collisionBox.addEventListener('mouseenter', (e) => {
baseCard.style.transition = 'none';
//z akseli nostot pohja kortista
title.style.transform = 'translateZ(70px) translateX(260px)';
info.style.transform = 'translateZ(70px)';
logo.style.transform = 'translateZ(130px)';
button.style.transform = 'translateZ(100px)';

})

collisionBox2.addEventListener('mouseenter', (e) => {
baseCard2.style.transition = 'none';
//z akseli nostot pohja kortista
title2.style.transform = 'translateZ(100px) translateX(280px)';
info2.style.transform = 'translateZ(70px)';
logo2.style.transform = 'translateZ(130px)';
button2.style.transform = 'translateZ(70px)';
})



//when moving out of collisionBox palaa takaisin rauhallisesti nykimättä
collisionBox.addEventListener('mouseleave', (e) => {
baseCard.style.transform = `rotateY(0deg) rotateX(0deg)`;
//lisää smoothisti palaamisen päälle (kunnes mouse-enteri taas poistaa sen!)
baseCard.style.transition = 'all 0.5s ease';
title.style.transform = 'translateZ(0px)';
info.style.transform = 'translateZ(0px)';
logo.style.transform = 'translateZ(0px) rotateZ(0deg)';
button.style.transform = 'translateZ(0px)';

})

collisionBox2.addEventListener('mouseleave', (e) => {
baseCard2.style.transform = `rotateY(0deg) rotateX(0deg)`;
//lisää smoothisti palaamisen päälle (kunnes mouse-enteri taas poistaa sen!)
baseCard2.style.transition = 'all 0.5s ease';
title2.style.transform = 'translateZ(0px)';
info2.style.transform = 'translateZ(0px)';
logo2.style.transform = 'translateZ(0px) rotateZ(0deg)';
button2.style.transform = 'translateZ(0px)';
})