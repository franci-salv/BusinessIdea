import { useState } from "react";
import { db } from "../firebase";
import { collection, addDoc } from "firebase/firestore";

const handleStripeCheckout = () => {
  window.open("https://buy.stripe.com/5kQ8wH8aF9Nu4mS6Sg73G00", "_blank");
};

export default function SignupForm() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!phone.match(/^\+\d{6,15}$/)) {
      alert("Please enter your phone number in international format (e.g. +49123456789)");
      return;
    }

    if (!language) {
      alert("Please select a language.");
      return;
    }

    try {
      await addDoc(collection(db, "subscribers"), {
        name,
        phone,
        language,
        timestamp: new Date()
      });

      alert("You're signed up! ✅");
      setName("");
      setPhone("");
      setLanguage("");
    } catch (err) {
      console.error("Error saving to Firestore:", err);
      alert("Oops, something went wrong. Try again later.");
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-md p-8 bg-white shadow-lg rounded-2xl space-y-6 flex flex-col">
        <h1 className="text-2xl font-bold text-center text-gray-800">
          🧠 Daily Puzzle Signup
        </h1>

        <form onSubmit={handleSubmit} className="space-y-5 w-full">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. Anna"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">WhatsApp Number</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              placeholder="+49123456789"
              className="mt-1 w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring focus:ring-blue-300"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Preferred Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              required
              className="mt-1 w-full border border-gray-300 rounded-lg p-2 bg-white focus:outline-none focus:ring focus:ring-blue-300"
            >
              <option value="">-- Select --</option>
              <option value="en">English</option>
              <option value="it">Italiano</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 text-sm">
            <input type="checkbox" required />
            <label>I agree to receive messages on WhatsApp</label>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 text-white font-semibold py-2 rounded-lg hover:bg-blue-700 transition"
          >
            Submit
          </button>
        </form>

        <hr className="border-t mt-4 w-full" />

        <div className="text-center w-full">
          <button
            onClick={handleStripeCheckout}
            className="w-full bg-green-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-green-700 transition"
          >
            Subscribe for €3/month
          </button>
        </div>

        <p className="text-xs text-gray-500 text-center">
          You’ll receive 3 brain teasers every day via WhatsApp. Cancel anytime.
        </p>
      </div>
    </div>
  );
}
