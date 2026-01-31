
import AnimatedAIChat from './components/mvpblocks/animated-ai-chat';
import Aurora from './components/Aurora';
import './App.css';

function App() {
  return (
    <div className="bg-background text-foreground relative min-h-screen w-full overflow-hidden">
      <div className="absolute inset-0 z-0">
        <Aurora
          colorStops={['#E0AA0F', '#000000', '#E0AA0F']}
          speed={0.5}
        />
      </div>
      <div className="relative z-10 w-full h-full">
        <AnimatedAIChat />
      </div>
    </div>
  );
}

export default App;
