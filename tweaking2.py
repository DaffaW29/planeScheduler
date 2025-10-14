import json
import sys

PLANE_UNLOAD_TIME = 20
TRUCK_LOAD_TIME = 5

# Load the json files for use
def load_data(meta_path, aircraft_path, trucks_path):
    with open(meta_path, 'r') as f:
        meta_data = json.load(f)
    with open(aircraft_path, 'r') as f:
        aircraft_data = json.load(f)
    with open(trucks_path, 'r') as f:
        truck_data = json.load(f)
    return meta_data, aircraft_data, truck_data

# Defining variables
def define_variables(meta_data, aircraft_data, truck_data):
    variables = []
    forklifts = meta_data['Forklift']
    
    # Plane and truck hangar and arrival time variables
    for plane in aircraft_data:
        variables.append(f'{plane}_Departure_Time')

        for hangar in meta_data['Hangars']:
            variables.append(f'{plane}_{hangar}_Arrival_Time')

        for i in range(aircraft_data[plane]['Cargo']):
            for fork in forklifts:
                variables.append(f'{plane}_Unload_{i}_Time_{fork}')

    for truck in truck_data:
        variables.append(f'{truck}_Departure_Time')

        for hangar in meta_data['Hangars']:
            variables.append(f'{truck}_{hangar}_Arrival_Time')

        for fork in forklifts:
            variables.append(f'{truck}_Load_Time_{fork}')
        
    return variables

# Defining domains for these variables
def define_domains(meta_data, aircraft_data, truck_data):
    domains = {}
    
    start_time = meta_data['Start Time']
    stop_time = meta_data['Stop Time']
    current_time = start_time
    time_schedule = []

    while current_time <= stop_time:
        time_schedule.append(current_time)
        current_time += 5

    all_vars = define_variables(meta_data, aircraft_data, truck_data)

    for var in all_vars:
        domains[var] = time_schedule

    return domains

# Helper functions for the constraint checker
#this will return the occupied hangar intervals for each hangar which are important for handling overlap
# Returns sum like {'The Hangar': [(800, 840), (900, 930)], ...}
# def get_vehicle_timeline(assignments, problem_data):
#     hangar_schedule = {h: {'planes': [], 'trucks': []} for h in problem_data['meta']['Hangars']}
#     vehicle_tasks = {}
    
#     for var, val in assignments.items():
#         if 'Unload_Pallet_' in var or 'Load_Pallet_' in var:
#             vehicle_name = var.split('_')[-1]
#             if vehicle_name not in vehicle_tasks:
#                 vehicle_tasks[vehicle_name] = []
#             vehicle_tasks[vehicle_name].append((var, val))
    
#     for vehicle, tasks in vehicle_tasks.items():
#         if not tasks: continue
        
#         assigned_hangar = assignments.get(f'{vehicle}_Hangar')
#         if not assigned_hangar: continue

#         start_times = [task_val[2] for _task_var, task_val in tasks]
#         end_times = [task_val[2] + (20 if 'Unload' in task_var else 5) for task_var, task_val in tasks]
        
#         occupied_start = min(start_times)
#         occupied_end = max(end_times)

#         if vehicle in problem_data['aircraft']:
#             hangar_schedule[assigned_hangar]['planes'].append((occupied_start, occupied_end))
#         elif vehicle in problem_data['trucks']:
#             hangar_schedule[assigned_hangar]['trucks'].append((occupied_start, occupied_end))

#     return hangar_schedule

def parse_variable(variable, problem_data):
    parts = variable.split("_")
    info = {"plane": None, "truck": None, "hangar": None, "forklift": None, "type": None, "index": None}

    if "Unload" in parts:
        # plane unload variable
        info["type"] = "Unload"
        info["plane"] = parts[0]
        info["index"] = parts[2]  # numeric pallet index
        info["forklift"] = parts[-1]
    elif "Load" in parts:
        # truck load variable
        info["type"] = "Load"
        info["truck"] = parts[0]
        info["forklift"] = parts[-1]
    elif "Arrival" in parts:
        # plane or truck arrival variable
        info["type"] = "Arrival"
        if parts[0] in problem_data["aircraft"]:
            info["plane"] = parts[0]
        else:
            info["truck"] = parts[0]
        info["hangar"] = parts[1]
    elif "Departure" in parts:
        # plane or truck departure variable
        info["type"] = "Departure"
        if parts[0] in problem_data["aircraft"]:
            info["plane"] = parts[0]
        else:
            info["truck"] = parts[0]

    return info

def same_vehicle(variable1, variable2):
    return (variable1.get('truck') and variable1['truck'] == variable2['truck']) or (variable1.get('plane') and variable1['plane'] == variable2['plane'])

# #Another helper function like hangar occupied but for forklifts
# def get_occupied_forklift_intervals(assignments):
#     forklift_schedule = {}
#     for var, val in assignments.items():
#         if 'Unload_Pallet_' in var or 'Load_Pallet_' in var:
#             forklift, _hangar, start_time = val
#             if forklift not in forklift_schedule:
#                 forklift_schedule[forklift] = []
#             end_time = start_time + (20 if 'Unload' in var else 5)
#             forklift_schedule[forklift].append((start_time, end_time))
#     return forklift_schedule

# The constraint checker
#Next is the constraint checker which will be extremely important as it will be pretty much called every time something is passed through the main alg
#idea is the checker will take a variable such as Plane1_Hangar-Arrival_Time, a value from that vars domain so like one of the possible times 800
#the assigmnets which are the approved actions so far in the schdule which will compare for conflicts with those, and the problem data so like the general data from JSON
def meets_constraints(variable, value, assignments, problem_data):
    info = parse_variable(variable, problem_data)

    # Cannot arrived before arrival time
    # Cannot arrive after already arrived
    # Cannot arrive at hangar with plane in it
    if info['type'] == 'Arrival':
         # Ensure no arrival before designated arrival time
        if info.get('truck'):
            original_arrival_time = problem_data['trucks'].get(info.get('truck'))
        else:
            original_arrival_time = problem_data['aircraft'].get(info.get('plane'), {}).get('Time')

        if value < original_arrival_time:
            return False
        
        plane_arrivals = plane_departures = 0
        truck_arrivals = truck_departures = 0

        # Ensure no prior arrival of the same vehicle
        for assignment, time in assignment.items():
            assignment_info = parse_variable(assignment, problem_data)
            
            if assignment_info['type'] == 'Arrival':
                if same_vehicle(info, assignment_info):
                    return False
                
                if info['hangar'] == assignment_info['hangar']:
                    if info.get('truck'):
                        truck_arrivals += 1
                    else:
                        plane_arrivals += 1
                        

            if assignment_info['type'] == 'Departure' and info['hangar'] == assignment_info['hangar']:
                if info.get('truck'):
                    truck_departures += 1
                else:
                    plane_departures += 1

        # If arrivals != departures, then there must be a plane/truck at the hangar already
        if ((info.get('plane') and plane_arrivals != plane_departures) or
            (info.get('truck') and truck_arrivals != truck_departures)):
            return False


    # Cannot depart before arriving
    # Cannot depart with cargo
    if info['type'] == 'Departure':
        # Ensure arrival before departure and cargo fully unloaded if a plane departure
        # No check for prior departures as only one departure variable exists per vehicle
        valid_arrival = False
        cargo_loaded = 0

        for assignment, time in assignments.items():
            assignment_info = parse_variable(assignment, problem_data)

            if not same_vehicle(info, assignment_info):
                continue

            if assignment_info['type'] == 'Arrival' and time < value:
                valid_arrival = True

            if assignment_info['type'] == 'Unload':
                cargo_loaded += 1

        if not valid_arrival or (info.get("plane") and cargo_loaded != problem_data['aircraft'][info['plane']]['Cargo']):
            return False

    # Cannot load departed truck
    # Cannot load loaded truck
    # Cannot load with in-use forklift
    # (TODO) Cannot load if no cargo at hangar
    if info['type'] == 'Load':
        # If loading finishes after our time deadline
        if value + TRUCK_LOAD_TIME > problem_data['Meta']['Stop Time']:
            return False

        valid_arrival = False

        for assignment, time in assignments.items():
            assignment_info = parse_variable(assignment, problem_data)

            if assignment_info.get('forklift') and info['forklift'] == assignment_info['forklift']:
                fork_finished_use = time + (PLANE_UNLOAD_TIME if assignment_info['type'] == 'Unload' else TRUCK_LOAD_TIME)
                
                # If forklift is in use during the time
                # Essentially if it finishes after this previous forklift assignment started,
                # but before it ended. May be possible to remove "value + TRUCK_LOAD_TIME > time"
                # and force forklift assignments to be added in order.
                # Not sure if that would improve efficiency or even work.
                if value + TRUCK_LOAD_TIME > time and value < fork_finished_use:
                    return False

            if same_vehicle(info, assignment_info):
                # If the truck has already departed or if its already been loaded, it cannot be loaded
                if assignment_info['type'] in ['Departure', 'Load']:
                    return False
                
                if assignment_info['type'] == 'Arrival':
                    # If we are trying to load before the truck arrives
                    if value < time:
                        return False
                    
                    valid_arrival = True

        if not valid_arrival:
            return False
        
    if info['type'] == 'Unload':
        # If unloading + loading is not feasible before time deadline
        if value + PLANE_UNLOAD_TIME + TRUCK_LOAD_TIME > problem_data['Meta']['Stop Time']:
            return False

    return True

# The backtracking solver
#Now that i think ive got a decent constraint checker, we create the csp backtracker 
def solve_csp(assignments, variables, domains, problem_data):
    # Base case: All variables have been assigned.
    # if not variables:
    #     return assignments
    loaded = set()

    for assignment in assignments.keys():
        if assignment.startswith('Load_Pallet_'):
            loaded.add(assignment.split('_')[2])

    if len(loaded) == sum(data['Cargo'] for data in problem_data['aircraft'].values()):
        return assignments

    # pick the first unassigned var to use
    variable = variables[0]

    # Iterate through the domain of the selected variable. (So like if its Plane1_Hangar youll iterate between hangar1 hangar 2 etc)
    for value in domains[variable]:
        # check constraints
        if meets_constraints(variable, value, assignments, problem_data):
            # If consistent, prematurely add the assignment and do recursion
            assignments[variable] = value
            result = solve_csp(assignments, variables[1:], domains, problem_data)
            # print("CSP RESULTS")
            # print(assignments)

            # If the recursive call finds a solution return
            if result is not None:
                return result

            # If the recursive call fails go back and delete the premature assignment
            del assignments[variable]

    
    # If the loop finishes without finding a solution, return None.
    return None







# The output formatter (ABSOLUTELY CHATTED)
def format_solution(assignments, problem_data):
    schedule = {
        "aircraft": {},
        "trucks": {},
        "forklifts": {fork: [] for fork in problem_data['meta']['Forklifts']}
    }
    
    pallet_tasks_by_plane = {plane: [] for plane in problem_data['aircraft']}
    pallet_tasks_by_truck = {truck: [] for truck in problem_data['trucks']}
    
    for var, val in assignments.items():
        if 'Unload_Pallet_' in var:
            plane_name = var.split('_')[-1]
            pallet_tasks_by_plane[plane_name].append((var, val))
        elif 'Load_Pallet_' in var:
            truck_name = var.split('_')[-1]
            pallet_tasks_by_truck[truck_name].append((var, val))
    
    for vehicle_name in list(problem_data['aircraft'].keys()) + list(problem_data['trucks'].keys()):
        hangar = assignments.get(f'{vehicle_name}_Hangar')
        tasks = pallet_tasks_by_plane.get(vehicle_name, []) or pallet_tasks_by_truck.get(vehicle_name, [])
        
        if not tasks: 
            if vehicle_name in problem_data['aircraft']:
                schedule['aircraft'][vehicle_name] = {}
            else:
                schedule['trucks'][vehicle_name] = {}
            continue

        start_times = [task_val[2] for _task_var, task_val in tasks]
        end_times = [task_val[2] + (20 if 'Unload' in task_var else 5) for task_var, task_val in tasks]
        
        arrival = min(start_times) if start_times else assignments.get(f'{vehicle_name}_Hangar_Arrival_Time')
        departure = max(end_times) if end_times else assignments.get(f'{vehicle_name}_Hangar_Arrival_Time')
        
        vehicle_schedule = {
            "Hangar": hangar,
            "Arrival": arrival,
            "Departure": departure
        }

        if vehicle_name in problem_data['aircraft']:
            schedule['aircraft'][vehicle_name] = vehicle_schedule
        else:
            schedule['trucks'][vehicle_name] = vehicle_schedule

    for var, val in assignments.items():
        if 'Unload_Pallet_' in var or 'Load_Pallet_' in var:
            forklift, hangar, start_time = val
            job_type = "Unload" if 'Unload' in var else "Load"
            
            schedule['forklifts'][forklift].append({
                "Hangar": hangar,
                "Time": start_time,
                "Job": job_type
            })
    
    for fork in schedule['forklifts']:
        schedule['forklifts'][fork].sort(key=lambda x: x['Time'])
        
    return schedule






if __name__ == "__main__":
        
    meta_path = sys.argv[1]
    aircraft_path = sys.argv[2]
    trucks_path = sys.argv[3]
    schedule_path = sys.argv[4]

    try:
        meta_data, aircraft_data, truck_data = load_data(meta_path, aircraft_path, trucks_path)
        problem_data = {
            "meta": meta_data,
            "aircraft": aircraft_data,
            "trucks": truck_data
        }
    except FileNotFoundError as e:
        print("Dumbass")
        sys.exit(1)

    all_variables = define_variables(meta_data, aircraft_data, truck_data)
    domains = define_domains(meta_data, aircraft_data, truck_data)

    solution = solve_csp({}, all_variables, domains, problem_data)

    if solution is not None:
        print("Solution found!")
        schedule_output = format_solution(solution, problem_data)
        try:
            with open(schedule_path, 'w') as f:
                json.dump(schedule_output, f, indent=2)
            print(f"Schedule successfully written to {schedule_path}")
        except IOError as e:
            print(f"Error writing to file: {e}")
            sys.exit(1)
    else:
        print("No solution found for this problem.")
        try:
            with open(schedule_path, 'w') as f:
                json.dump({}, f)
        except IOError as e:
            print(f"Error writing to file: {e}")
            sys.exit(1)