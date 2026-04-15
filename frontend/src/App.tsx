import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Hero from './components/Hero';
import Challenge from './components/Challenge';
import Solution from './components/Solution';
import Capabilities from './components/Capabilities';
import Footer from './components/Footer';
import DeployAgent from './components/DeployAgent';

function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Challenge />
        <Solution />
        <Capabilities />
      </main>
      <Footer />
    </>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/deploy" element={<DeployAgent />} />
      </Routes>
    </Router>
  );
}

export default App;
