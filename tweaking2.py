import json
import sys
from itertools import product


TIME_STEP = 5

PLANE_UNLOAD_TIME = TIME_STEP*4
TRUCK_LOAD_TIME = TIME_STEP*1
PLANE_UNLOAD_DURATION = 20
TRUCK_LOAD_DURATION = 5

# Load the json files for use
def load_data(meta_path, aircraft_path, trucks_path):
    with open(meta_path, 'r') as f:
        meta_data = json.load(f)
    with open(aircraft_path, 'r') as f:
        aircraft_data = json.load(f)
    with open(trucks_path, 'r') as f:
        truck_data = json.load(f)
    return meta_data, aircraft_data, truck_data

#Time managemenr helpers 
def increment_time(current):
    hours = current // 100
    minutes = current % 100

    minutes += 5
    if minutes >= 60:
        hours += 1
        minutes -= 60

    return hours * 100 + minutes


def define_variables(meta_data, aircraft_data, truck_data):
    #Defines variables based on key decisions for each plane and pallet.
    variables = []
    pallets = []
    for plane, details in aircraft_data.items():
        for i in range(details['Cargo']):
            pallets.append(f"{plane}_Pallet_{i}")
            
    # Plane arrival at hangar
    for plane in aircraft_data:
        variables.append(f"Plane_Arrival_{plane}")
        
    # Truck arrival at a hangar
    for truck in truck_data:
        variables.append(f"Truck_Hangar_Arrival_{truck}")
        
	#everything done by pallet
    # For each individual pallet, we have three things to deyermin
    for pallet_id in pallets:
        # WHICH truck will carry pallet
        variables.append(f"Pallet_Assignment_{pallet_id}")

        #WHO UNLOADS the pallet and WHEN
        variables.append(f"Unload_Task_{pallet_id}")

        # WHO LOADS this pallet and WHEN
        variables.append(f"Load_Task_{pallet_id}")
        
    return variables
    
def define_domains(meta_data, aircraft_data, truck_data):
    domains = {}
    
    start_time = meta_data['Start Time']
    stop_time = meta_data['Stop Time']
    time_schedule = []
    current_time = start_time
    #account for time
    while current_time <= stop_time:
        time_schedule.append(current_time)
        current_time = increment_time(current_time)

    hangars = meta_data['Hangars']
    forklifts = meta_data['Forklifts']
    truck_names = list(truck_data.keys())
    pallets = []
    for plane, details in aircraft_data.items():
        for i in range(details['Cargo']):
            pallets.append(f"{plane}_Pallet_{i}")


    # Domain for Plane Arrival variables: (Hangar, Time)
    plane_arrival_domain = list(product(hangars, time_schedule))
    for plane in aircraft_data:
        var_name = f"Plane_Arrival_{plane}"
        #plane can't arrive at a hangar before it arrives at the terminal
        min_arrival_time = aircraft_data[plane]['Time']
        domains[var_name] = [
            (h, t) for h, t in plane_arrival_domain if t >= min_arrival_time
        ]
        
    # Domain for Truck Hangar Arrival: (Hangar, Time)
    truck_arrival_domain = list(product(hangars, time_schedule))
    for truck in truck_names:
        min_time = truck_data[truck]
        domains[f"Truck_Hangar_Arrival_{truck}"] = [(h, t) for h, t in truck_arrival_domain if t >= min_time]

    # Pallet Assignment variables: A list of truck names
    pallet_assignment_domain = truck_names
    
    #Unload/Load Task variables Forklift and Time
    task_domain = list(product(forklifts, time_schedule))

    # Assign domains to each pallet variable
    for pallet_id in pallets:
        domains[f"Pallet_Assignment_{pallet_id}"] = pallet_assignment_domain
        
        domains[f"Unload_Task_{pallet_id}"] = task_domain
        domains[f"Load_Task_{pallet_id}"] = task_domain
        
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

# def parse_variable(variable, problem_data):
#     parts = variable.split("_")
#     info = {"plane": None, "truck": None, "hangar": None, "forklift": None, "type": None, "index": None}

#     if "Unload" in parts:
#         # plane unload variable
#         info["type"] = "Unload"
#         info["plane"] = parts[0]
#         info["index"] = parts[2]  # numeric pallet index
#         info["forklift"] = parts[-1]
#     elif "Load" in parts:
#         # truck load variable
#         info["type"] = "Load"
#         info["truck"] = parts[0]
#         info["forklift"] = parts[-1]
#     elif "Arrival" in parts:
#         # plane or truck arrival variable
#         info["type"] = "Arrival"
#         if parts[0] in problem_data["aircraft"]:
#             info["plane"] = parts[0]
#         else:
#             info["truck"] = parts[0]
#         info["hangar"] = parts[1]
#     elif "Departure" in parts:
#         # plane or truck departure variable
#         info["type"] = "Departure"
#         if parts[0] in problem_data["aircraft"]:
#             info["plane"] = parts[0]
#         else:
#             info["truck"] = parts[0]

#     return info

def parse_variable(variable):
    parts = variable.split('_')
    info = {'type': parts[0] + '_' + parts[1]} # 'Plane_Arrival', 'Unload_Task', 'Load_Task', "Pallet_Assignment"
    
    if info['type'] == 'Plane_Arrival':
        info['plane'] = parts[2]
    elif info['type'] == 'Truck_Hangar': 
        info['truck'] = parts[3]
    elif info['type'] == 'Pallet_Assignment':
        info['pallet_id'] = f"{parts[2]}_{parts[3]}_{parts[4]}"
    elif info['type'] in ['Unload_Task', 'Load_Task']:
        info['pallet_id'] = f"{parts[2]}_{parts[3]}_{parts[4]}"
        info['plane'] = parts[2] 
        
    return info

def same_vehicle(variable1, variable2):
    return (variable1.get('truck') and variable1['truck'] == variable2['truck']) or (variable1.get('plane') and variable1['plane'] == variable2['plane'])

# The constraint checker
#Next is the constraint checker which will be extremely important as it will be pretty much called every time something is passed through the main alg
#idea is the checker will take a variable such as Plane1_Hangar-Arrival_Time, a value from that vars domain so like one of the possible times 800
#the assigmnets which are the approved actions so far in the schdule which will compare for conflicts with those, and the problem data so like the general data from JSON
# Define durations as constants for clarity

def meets_constraints(variable, value, assignments, problem_data):
   
    
    # If a variable is unassigned in the current branch, it's not a violation yet.
    if value is None:
        return True

    info = parse_variable(variable)
    stop_time = problem_data['meta']['Stop Time']

    # C1: CONSTRAINTS FOR 'Plane_Arrival' VARIABLES
    if info['type'] == 'Plane_Arrival':
        assigned_hangar, assigned_time = value

        # Rule: "Each terminal hangar can handle one aircraft at a time."
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue
            
            # Check against other assigned planes
            if 'Plane_Arrival' in other_var:
                other_info = parse_variable(other_var)
                other_hangar, other_time = other_val
                
                if assigned_hangar == other_hangar:
                    # To check for overlap, we need to know when the other plane DEPARTS.
                    # A plane departs after its last pallet is unloaded.
                    
                    # Find all pallets for the other plane
                    other_plane_pallets = [
                        p_var for p_var in assignments if f"Unload_Task_{other_info['plane']}_Pallet" in p_var
                    ]
                    
                    # Find the latest unload finish time for that plane's pallets
                    other_departure_time = other_time
                    for p_var in other_plane_pallets:
                        p_val = assignments.get(p_var)
                        if p_val:
                            _forklift, unload_start = p_val
                            unload_finish = unload_start + PLANE_UNLOAD_DURATION
                            if unload_finish > other_departure_time:
                                other_departure_time = unload_finish
                    
                    # The new plane can only arrive after the other plane departs.
                    if assigned_time < other_departure_time:
                        return False # Hangar conflict!

    # CONSTRAINTS FOR 'Pallet_Assignment' VARIABLES
    elif info['type'] == 'Pallet_Assignment':
        assigned_truck = value
        
        # Rule: "Each cargo truck can receive one pallet."
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue

            if 'Pallet_Assignment' in other_var and other_val == assigned_truck:
                return False 
            # Truck is already assigned to another pallet!
    
    # C3: CONSTRAINTS FOR 'Unload_Task' VARIABLES
    elif info['type'] == 'Unload_Task':
        assigned_forklift, unload_start_time = value

        # Rule: Unloading must finish by the stop time.
        if unload_start_time + PLANE_UNLOAD_DURATION > stop_time:
            return False

        # Rule: "No aircraft can unload before arriving at a hangar."
        plane_arrival_var = f"Plane_Arrival_{info['plane']}"
        plane_arrival_val = assignments.get(plane_arrival_var)
        if not plane_arrival_val:
            return False 
        
        # Trying to unload before the plane has arrived at the hangar.
        hangar, plane_arrival_time = plane_arrival_val
        if unload_start_time < plane_arrival_time:
            return False 
        
        # Rule: A forklift can only do one thing at a time.
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue
            
            if 'Unload_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                    # Check for time overlap
                    if max(unload_start_time, other_start_time) < min(unload_start_time + PLANE_UNLOAD_DURATION, other_start_time + PLANE_UNLOAD_DURATION):
                        return False 
            
            if 'Load_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                     if max(unload_start_time, other_start_time) < min(unload_start_time + PLANE_UNLOAD_DURATION, other_start_time + TRUCK_LOAD_DURATION):
                        return False 
                    
    #CONSTRAINTS FOR 'Truck_Hangar_Arrival' VARIABLES
    if info['type'] == 'Truck_Hangar':
        assigned_hangar, arrival_time = value
        departure_time = arrival_time + TRUCK_LOAD_DURATION

        # Rule: "Each hangar can accommodate one truck at any given time."
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue
            
            if 'Truck_Hangar_Arrival' in other_var:
                other_hangar, other_arrival = other_val
                if assigned_hangar == other_hangar:
                    other_departure = other_arrival + TRUCK_LOAD_DURATION
                    # Check for time overlap
                    if max(arrival_time, other_arrival) < min(departure_time, other_departure):
                        return False

    # C4: CONSTRAINTS FOR 'Load_Task' VARIABLES
    elif info['type'] == 'Load_Task':
        assigned_forklift, load_start_time = value

        # Rule: Loading must finish by the stop time.
        if load_start_time + TRUCK_LOAD_DURATION > stop_time:
            return False
        
        # Rule: Loading must happen after the pallet has been unloaded.
        unload_task_var = f"Unload_Task_{info['pallet_id']}"
        unload_task_val = assignments.get(unload_task_var)
        if not unload_task_val:
            return False 

        forklift, unload_start_time = unload_task_val
        unload_finish_time = unload_start_time + PLANE_UNLOAD_DURATION
        # Trying to load before unloading is finished.
        if load_start_time < unload_finish_time:
            return False 

        # Rule: "A forklift can only load if there is a truck waiting to be loaded"
        # This means the truck must have arrived at the terminal.
        pallet_assign_var = f"Pallet_Assignment_{info['pallet_id']}"
        assigned_truck = assignments.get(pallet_assign_var)
        if not assigned_truck:
            return False 
        
        truck_arrival_time = problem_data['trucks'][assigned_truck]
        if load_start_time < truck_arrival_time:
            return False 
        
        # Find that truck's scheduled arrival at the hangar
        truck_arrival_var = f"Truck_Hangar_Arrival_{assigned_truck}"
        truck_arrival_val = assignments.get(truck_arrival_var)
        if not truck_arrival_val: return False 

        truck_hangar, truck_hangar_arrival_time = truck_arrival_val
        
        #Rule: Truck's arrival should be the same time as the load
        if truck_hangar_arrival_time != load_start_time:
            return False
        
        # Rule: The truck must be at the same hangar where the pallet was unloaded.
        plane_arrival_var = f"Plane_Arrival_{info['plane']}"
        plane_hangar, _ = assignments.get(plane_arrival_var)
        if truck_hangar != plane_hangar:
            return False 

        # Rule: A forklift can only do one thing at a time. 
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue

            if 'Unload_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                    if max(load_start_time, other_start_time) < min(load_start_time + TRUCK_LOAD_DURATION, other_start_time + PLANE_UNLOAD_DURATION):
                        return False
            
            if 'Load_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                     if max(load_start_time, other_start_time) < min(load_start_time + TRUCK_LOAD_DURATION, other_start_time + TRUCK_LOAD_DURATION):
                        return False

    return True

# The backtracking solver
#Now that i think ive got a decent constraint checker, we create the csp backtracker 
# def solve_csp(assignments, variables, domains, problem_data):
#     # Base case: All variables have been assigned.
#     # if not variables:
#     #     return assignments
#     loaded = set()

#     for assignment in assignments.keys():
#         if assignment.startswith('Load_Pallet_'):
#             loaded.add(assignment.split('_')[2])

#     if len(loaded) == sum(data['Cargo'] for data in problem_data['aircraft'].values()):
#         return assignments

#     # pick the first unassigned var to use
#     variable = variables[0]

#     # Iterate through the domain of the selected variable. (So like if its Plane1_Hangar youll iterate between hangar1 hangar 2 etc)
#     for value in domains[variable]:
#         # check constraints
#         if meets_constraints(variable, value, assignments, problem_data):
#             # If consistent, prematurely add the assignment and do recursion
#             assignments[variable] = value
#             result = solve_csp(assignments, variables[1:], domains, problem_data)
#             # print("CSP RESULTS")
#             # print(assignments)

#             # If the recursive call finds a solution return
#             if result is not None:
#                 return result

#             # If the recursive call fails go back and delete the premature assignment
#             del assignments[variable]

    
#     # If the loop finishes without finding a solution, return None.
#     return None
#grab a 

# problem_data = {
#     "constraints": {
#         "X1": ["X2", "X3"],
#         "X2": ["X1"],
#         "check": lambda xi, xv, xj, yv: xv != yv  # example binary constraint
#     }
# }

# def ac3(domains, constraints):
#     """Primitive AC-3: reduces domains using binary constraints."""
#     queue = [(xi, xj) for xi in domains for xj in constraints.get(xi, [])]
#     inferences = []  # track all (var, value_removed) pairs
    
#     while queue:
#         xi, xj = queue.pop(0)
#         if revise(domains, xi, xj, constraints, inferences):
#             if not domains[xi]:  # domain wiped out → failure
#                 return None
#             for xk in constraints.get(xi, []):
#                 if xk != xj:
#                     queue.append((xk, xi))
#     return inferences  # return all pruned values


# def revise(domains, xi, xj, constraints, inferences):
#     revised = False
#     for x in domains[xi][:]:  # iterate over a copy
#         # if no value in Dj satisfies constraint between Xi=x and Xj=y
#         if not any(constraints["check"](xi, x, xj, y) for y in domains[xj]):
#             domains[xi].remove(x)
#             inferences.append((xi, x))  # record what was pruned
#             revised = True
#     return revised


# def restore_inferences(domains, inferences):
#     """Undo domain reductions."""
#     for var, value in inferences:
#         if value not in domains[var]:
#             domains[var].append(value)

def termination_condition(assignments, problem_data):
    # Terminate when all aircraft cargo loads have been completed
    loaded = set()
    for assignment in assignments.keys():
        if assignment.startswith('Load_Pallet_'):
            loaded.add(assignment.split('_')[2])

    total_cargo = sum(data['Cargo'] for data in problem_data['aircraft'].values())
    return len(loaded) == total_cargo

def solve_csp(assignments, variables, domains, problem_data):
    # Initialize latest_time on the first call
    
    # If no more variables, return None
    if not variables:
        return assignments

    variable = variables[0]
    domain = domains[variable]
    print(f"Jorkin it rn | Current Variable: {variable}        ", end="\r")

    # Iterate through the domain values in order
    for value in domain:
        # Check constraints
        if meets_constraints(variable, value, assignments, problem_data):
            assignments[variable] = value
            # inferences = ac3(domains, problem_data["constraints"])

            # if inferences is not None:
            result = solve_csp(assignments, variables[1:], domains, problem_data)

            if result is not None:
                return result

                # restore_inferences(domains, inferences)

            del assignments[variable]

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
        print(solution)
        print("Solution found!")
        # schedule_output = format_solution(solution, problem_data)
        # try:
        #     with open(schedule_path, 'w') as f:
        #         json.dump(schedule_output, f, indent=2)
        #     print(f"Schedule successfully written to {schedule_path}")
        # except IOError as e:
        #     print(f"Error writing to file: {e}")
        #     sys.exit(1)
    else:
        print("No solution found for this problem.")
        # try:
        #     with open(schedule_path, 'w') as f:
        #         json.dump({}, f)
        # except IOError as e:
        #     print(f"Error writing to file: {e}")
        #     sys.exit(1)