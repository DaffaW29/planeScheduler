import json
import sys

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
    
    # Plane and truck hangar and arrival time variables
    for plane_name in aircraft_data:
        variables.append(f'{plane_name}_Hangar')
        variables.append(f'{plane_name}_Hangar_Arrival_Time')

    for truck_name in truck_data:
        variables.append(f'{truck_name}_Hangar')
        variables.append(f'{truck_name}_Hangar_Arrival_Time')

    #going back to what was discussed in class, we wont model the variables based on the forklofts but rather the pallets 
    # idea: count num pallets from all aircraft which is also amt needed for truck,
    #Pallet vairables
    '''
    num_pallets = 0
    for j in aircraft_data:
        num_pallets += aircraft_data[j]['Cargo']
    
    for i in range(num_pallets):
        variables.append(f'Pallet_{i}_Forklifter')
        #this will be load or unload
        variables.append(f'Pallet_{i}_Action') 
        variables.append(f'Pallet_{i}_Hangar')
        variables.append(f'Pallet_{i}_StartTime')
    '''
    #originally I wanted to have the variables for pallets be per pallet, but i realized working on constraints it could get tedious so instead I made
    #pallet variables tied to the action and their respective plane/truck so wed have Load_Pallet_1_to_Truck67 etc
    pallet_count = 0 
    for plane_name, data in aircraft_data.items():
        for i in range(data['Cargo']):
            variables.append(f'Unload_Pallet_{pallet_count}_from_{plane_name}')
            pallet_count += 1
    
    total_unloaded_pallets = sum(data['Cargo'] for data in aircraft_data.values())
    truck_names = list(truck_data.keys())
    
    for i in range(total_unloaded_pallets):
        for truck in truck_names:
            variables.append(f'Load_Pallet_{i}_to_{truck}')
    print(variables)
    return variables

# Defining domains for these variables
def define_domains(meta_data, aircraft_data, truck_data):
    domains = {}
    hangars = meta_data['Hangars']
    forklifts = meta_data['Forklifts']
    time_schedule = []
    start_time = meta_data['Start Time']
    stop_time = meta_data['Stop Time']
    current_time = start_time
    while current_time <= stop_time:
        time_schedule.append(current_time)
        current_time += 5
        
    for plane in aircraft_data:
        domains[f'{plane}_Hangar'] = hangars
        domains[f'{plane}_Hangar_Arrival_Time'] = time_schedule
    
    for truck in truck_data:
        domains[f'{truck}_Hangar'] = hangars
        domains[f'{truck}_Hangar_Arrival_Time'] = time_schedule
    
    #domains for the pallets
    '''
    for i in range(num_pallets):
        domains[f'Pallet_{i}_Forklifter'] = forklifts
        domains[f'Pallet_{i}_Action'] = ["load", "unload"]
        domains[f'Pallet_{i}_Hangar'] = hangars
        domains[f'Pallet_{i}_StartTime'] = time_schedule
    '''
    #Used to be single, now we will create a domain for each of the actions which will consist of essentially the combinations of the possible times, hangar, forklift
    #for each action. this could lead to a super large domain down the line but for now we'll try it 

    all_vars = define_variables(meta_data, aircraft_data, truck_data)
    for var in all_vars:
        if var.startswith('Unload_Pallet_') or var.startswith('Load_Pallet_'):
            domain_options = []
            for fork in forklifts:
                for hangar in hangars:
                    for time in time_schedule:
                        domain_options.append((fork, hangar, time))
            domains[var] = domain_options
    
    return domains

# Helper functions for the constraint checker
#this will return the occupied hangar intervals for each hangar which are important for handling overlap
# Returns sum like {'The Hangar': [(800, 840), (900, 930)], ...}
def get_vehicle_timeline(assignments, problem_data):
    hangar_schedule = {h: {'planes': [], 'trucks': []} for h in problem_data['meta']['Hangars']}
    vehicle_tasks = {}
    
    for var, val in assignments.items():
        if 'Unload_Pallet_' in var or 'Load_Pallet_' in var:
            vehicle_name = var.split('_')[-1]
            if vehicle_name not in vehicle_tasks:
                vehicle_tasks[vehicle_name] = []
            vehicle_tasks[vehicle_name].append((var, val))
    
    for vehicle, tasks in vehicle_tasks.items():
        if not tasks: continue
        
        assigned_hangar = assignments.get(f'{vehicle}_Hangar')
        if not assigned_hangar: continue

        start_times = [task_val[2] for _task_var, task_val in tasks]
        end_times = [task_val[2] + (20 if 'Unload' in task_var else 5) for task_var, task_val in tasks]
        
        occupied_start = min(start_times)
        occupied_end = max(end_times)

        if vehicle in problem_data['aircraft']:
            hangar_schedule[assigned_hangar]['planes'].append((occupied_start, occupied_end))
        elif vehicle in problem_data['trucks']:
            hangar_schedule[assigned_hangar]['trucks'].append((occupied_start, occupied_end))

    return hangar_schedule


#Another helper function like hangar occupied but for forklifts
def get_occupied_forklift_intervals(assignments):
    forklift_schedule = {}
    for var, val in assignments.items():
        if 'Unload_Pallet_' in var or 'Load_Pallet_' in var:
            forklift, _hangar, start_time = val
            if forklift not in forklift_schedule:
                forklift_schedule[forklift] = []
            end_time = start_time + (20 if 'Unload' in var else 5)
            forklift_schedule[forklift].append((start_time, end_time))
    return forklift_schedule

# The constraint checker
#Next is the constraint checker which will be extremely important as it will be pretty much called every time something is passed through the main alg
#idea is the checker will take a variable such as Plane1_Hangar-Arrival_Time, a value from that vars domain so like one of the possible times 800
#the assigmnets which are the approved actions so far in the schdule which will compare for conflicts with those, and the problem data so like the general data from JSON
def meets_constraints(variable, value, assignments, problem_data):
    # Check 1: Vehicle Terminal Arrival Time
    if 'Hangar_Arrival_Time' in variable:
        vehicle = variable.split('_')[0]
        original_arrival_time = problem_data['aircraft'].get(vehicle, {}).get('Time') or problem_data['trucks'].get(vehicle)
        if value < original_arrival_time:
            return False

    # Check 2: Task Hangar Location vs. Vehicle Hangar Location
    if 'Unload_Pallet_' in variable or 'Load_Pallet_' in variable:
        _forklift, proposed_hangar, _start_time = value
        vehicle_name = variable.split('_')[-1]
        
        hangar_var = f'{vehicle_name}_Hangar'
        # Can't check yet
        # if hangar_var not in assignments:
        #     return True 

        assigned_hangar = assignments[hangar_var]
        if proposed_hangar != assigned_hangar:
            return False

    # Check 3: Task Start Time vs. Vehicle Hangar Arrival Time
    if 'Unload_Pallet_' in variable or 'Load_Pallet_' in variable:
        _forklift, _hangar, start_time = value
        vehicle_name = variable.split('_')[-1]
        
        arrival_var = f'{vehicle_name}_Hangar_Arrival_Time'
        # if arrival_var not in assignments:
        #     return True 

        vehicle_hangar_arrival = assignments[arrival_var]
        if start_time < vehicle_hangar_arrival:
            return False
    
    # Check 4: Hangar Occupancy (Plane-Plane and Truck-Truck conflicts)
    if 'Unload_Pallet_' in variable or 'Load_Pallet_' in variable:
        vehicle_name = variable.split('_')[-1]
        new_hangar = assignments.get(f'{vehicle_name}_Hangar')
        # if not new_hangar: return True

        is_plane = vehicle_name in problem_data['aircraft']
        vehicle_timeline = get_vehicle_timeline(assignments, problem_data)
        
        # Check for conflicts with vehicles of the same type
        if is_plane:
            intervals_to_check = vehicle_timeline.get(new_hangar, {}).get('planes', [])
        else:
            intervals_to_check = vehicle_timeline.get(new_hangar, {}).get('trucks', [])
        
        new_start_time = value[2]
        new_end_time = new_start_time + (20 if 'Unload' in variable else 5)
        
        for existing_start, existing_end in intervals_to_check:
            if new_start_time < existing_end and existing_start < new_end_time:
                return False
            
    # Check 5: Forklift Availability
    if 'Unload_Pallet_' in variable or 'Load_Pallet_' in variable:
        new_forklift, _hangar, new_start_time = value
        occupied_intervals = get_occupied_forklift_intervals(assignments)
        #check overlaps
        for existing_start, existing_end in occupied_intervals.get(new_forklift, []):
            new_end_time = new_start_time + (20 if 'Unload' in variable else 5)
            if new_start_time < existing_end and existing_start < new_end_time:
                return False 

    # Check 6: Pallet Availability (Unload Before Load)
    if 'Load_Pallet_' in variable:
        _forklift, _hangar, new_start_time = value
        unloaded_count = 0
        loaded_count = 0
        
        for assigned_var, assigned_val in assignments.items():
            if 'Unload_Pallet_' in assigned_var and len(assigned_val) == 3:
                unload_finish_time = assigned_val[2] + 20
                if unload_finish_time <= new_start_time:
                    unloaded_count += 1
            elif 'Load_Pallet_' in assigned_var and len(assigned_val) == 3:
                load_finish_time = assigned_val[2] + 5
                if load_finish_time <= new_start_time:
                    loaded_count += 1
        
        if unloaded_count <= loaded_count:
            return False
            
    # Check 7: Stay within airport operating hours
    if 'Unload_Pallet_' in variable or 'Load_Pallet_' in variable:
        _forklift, _hangar, start_time = value
        end_time = start_time + (20 if 'Unload' in variable else 5)
        if end_time > problem_data['meta']['Stop Time']:
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