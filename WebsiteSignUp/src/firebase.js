// src/firebase.js
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
// import { getAnalytics } from "firebase/analytics"; // Optional – not needed for MVP

const firebaseConfig = {
  apiKey: "AIzaSyBogJ3uG5d07LbLuD4H057fGPr9zY88cNk",
  authDomain: "daily-puzzle-business.firebaseapp.com",
  projectId: "daily-puzzle-business",
  storageBucket: "daily-puzzle-business.firebasestorage.app",
  messagingSenderId: "535940168207",
  appId: "1:535940168207:web:76eaa62429e9cf7bc8817a",
  measurementId: "G-HY12DKPMTS"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// ✅ Export auth and db
export const auth = getAuth(app);
export const db = getFirestore(app);
