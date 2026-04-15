import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import Header from './components/Header';
import Hero from './components/Hero';
import Challenge from './components/Challenge';
import Solution from './components/Solution';
import Capabilities from './components/Capabilities';
import Footer from './components/Footer';
import DeployAgent from './components/DeployAgent';

function ScrollHandler() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      setTimeout(() => {
        const id = hash.replace('#', '');
        const element = document.getElementById(id);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' });
        }
      }, 0);
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);

  return null;
}

function Home() {
  return (
    <div className="bg-gradient-to-b from-[#050505] via-[#101010] to-[#0a0a0a]">
      <Header />
      <main>
        <Hero />
        <Challenge />
        <Solution />
        <Capabilities />
      </main>
      <Footer />
    </div>
  );
}

function App() {
  return (
    <Router>
      <ScrollHandler />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/deploy" element={<DeployAgent />} />
      </Routes>
    </Router>
  );
}

export default App;
