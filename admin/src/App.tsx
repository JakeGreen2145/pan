import { useState } from 'react';
import { Layout } from './components/Layout';
import { HouseManager } from './pages/HouseManager';

function App() {
  const [activeTab, setActiveTab] = useState('house-manager');

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === 'house-manager' && <HouseManager />}
      {activeTab === 'tech-chair' && <div>Tech Chair UI Coming Soon</div>}
      {activeTab === 'settings' && <div>Settings UI Coming Soon</div>}
    </Layout>
  );
}

export default App;
