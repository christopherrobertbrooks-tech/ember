import cProfile
import pstats
import io
import time
from memory_profiler import profile
from ember_engine import EmberCore

@profile
def run_mock_session():
    print("Initializing EmberCore...")
    engine = EmberCore()
    
    # Init memory and simple models to profile
    # (assuming init_memory doesn't take forever, or it just sets up Chroma)
    engine.init_memory()
    
    # We will mock a few memory saving calls
    print("Running memory operations...")
    for i in range(10):
        engine.save_memory(f"Test memory {i}: The user likes the color blue and reading books.")
        
    print("Mock session complete.")

if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    run_mock_session()
    pr.disable()
    
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20) # print top 20
    
    with open("profile_results.txt", "w") as f:
        f.write(s.getvalue())
    print("Profiling results saved to profile_results.txt")
