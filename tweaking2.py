import json
import sys
from itertools import product


'''
Homework 3: Terminal Scheduler Daffa W + George C

Notes of other sources:

Pallet Domain Section:
#originally we tried AC3, when that didnt work, I tried to implement forward checking after seeing it on the CMU website https://www.cs.cmu.edu/~15281-s23/coursenotes/constraints/index.html
    #but when I failed that MISERABLY, i ended up thinking maybe we can chop off time limiting restrictions from the get go, we pruned the arrival domains based on arrival times, why dont
    #we do the same with the pallet load and unload times?

Constraint Section:
#Next is the constraint checker which will be extremely important as it will be pretty much called every time something is passed through the main alg
#idea is the checker will take a variable such as Plane1_Hangar-Arrival_Time, a value from that vars domain so like one of the possible times 800
#the assigmnets which are the approved actions so far in the schdule which will compare for conflicts with those, and the problem data so like the general data from JSON
# I had a bit of trouble understanding how  this function would be structured when i made my first attempt. So what I used a blueprint from geeksforgeeks
#https://www.geeksforgeeks.org/artificial-intelligence/constraint-satisfaction-problems-csp-in-artificial-intelligence/
# but rather than having constraints be their own separate thing, i ended up putting them all in one function. Later when we revamped our vars, i then sectioned the 
#constraint out in terms of which variable they appplied to 

Attempt at AC3 near end:
#we tried to do AC3 to speed up time but ended up settling by instead just pruning the domain to have less value options to run through, this ended up saving us the time
#a link I referenced for the AC3 came from berkeley https://inst.eecs.berkeley.edu/~cs188/textbook/csp/filtering.html


# The output formatter
#writing into a json file in python is something pretty foreign to me so i had to utilize outside resources from google to understand how to get it in the 
#format I was looking for. the biggest help was this geeks for geeks website https://www.geeksforgeeks.org/python/reading-and-writing-json-to-a-file-in-python/
#which actually had a close to ideal template for me to use for the formatter.



'''


TIME_STEP = 5

PLANE_UNLOAD_TIME = TIME_STEP*4
TRUCK_LOAD_TIME = TIME_STEP*1

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

#conversion time which i needed for anything that involved adding 
def convert_time(current):
    hours = current // 100
    minutes = current % 100

    if minutes >= 60:
        hours += 1
        minutes -= 60

    return hours * 100 + minutes


def define_variables(meta_data, aircraft_data, truck_data):
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
        
	#everything based on pallet as mentioned in class, we decided to make the variables based on the main actions and the truck
    #originally, we had it so we had a variable for every UNIQUE combo of load and truck such as Load_Pallet_1_Truck_1 with a single time value
    # which led to a bunch of unassigned variables in a solution so we made them more broad with tuples as vals when needed
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
            (hangar, time) for hangar, time in plane_arrival_domain if time >= min_arrival_time
        ]
        
    # Domain for Truck Hangar Arrival: (Hangar, Time), exact same as plane
    truck_arrival_domain = list(product(hangars, time_schedule))
    for truck in truck_names:
        min_time = truck_data[truck]
        domains[f"Truck_Hangar_Arrival_{truck}"] = [(hangar, time) for hangar, time in truck_arrival_domain if time >= min_time]

    # Domain for Pallet Specific Variables
    
    #originally we tried AC3, when that didnt work, I tried to implement forward checking after seeing it on the CMU website https://www.cs.cmu.edu/~15281-s23/coursenotes/constraints/index.html
    #but when I failed that MISERABLY, i ended up thinking maybe we can chop off time limiting restrictions from the get go, we pruned the arrival domains based on arrival times, why dont
    #we do the same with the pallet load and unload times?
    
    # Find the latest possible time a load can START
    latest_load_start = -1
    for t in reversed(time_schedule):
        if convert_time(t + TRUCK_LOAD_TIME) <= stop_time:
            latest_load_start = t
            #once ya find litterally stop
            break
    #The latest an unload can finish is also the latest a load can start oooooooo
    latest_unload_finish = latest_load_start
            
    
    # given we found when it can last finish we now find the latest possible time an unload can start
    latest_unload_start = -1
    # Only search if loading is even possible
    if latest_unload_finish != -1:
        for t in reversed(time_schedule):
            if convert_time(t + PLANE_UNLOAD_TIME) <= latest_unload_finish:
                latest_unload_start = t
                break
    
    # Create the new pruned domains
    # this is why i have the -1 for initiallization, clearly if nothing works we'll quickly see an empty domain and fail (part 5)
    pruned_unload_domain = [
        (forklift, time) for forklift, time in product(forklifts, time_schedule) if time <= latest_unload_start
    ]
    
    pruned_load_domain = [
        (forklift, time) for forklift, time in product(forklifts, time_schedule) 
        if time <= latest_load_start
    ]

    #Assign the new domains to the respective pallets taking into the consideration the time of plane/trucl arrival
    for pallet_id in pallets:
        domains[f"Pallet_Assignment_{pallet_id}"] = truck_names
        
        # Plane arrival for unload
        plane_name = pallet_id.split('_Pallet_')[0]
        min_unload_start = aircraft_data[plane_name]['Time']
        
        domains[f"Unload_Task_{pallet_id}"] = [
            (forklift, time) for forklift, time in pruned_unload_domain if time >= min_unload_start
        ]
        
        # Truck arrival for load
        pruned_load_domain_for_pallet = []
        for truck_name in truck_names:
            min_load_start = truck_data[truck_name]
            for f, t in pruned_load_domain:
                if t >= min_load_start:
                    pruned_load_domain_for_pallet.append((f,t))
        
        # remove duplicates from the list w set
        domains[f"Load_Task_{pallet_id}"] = list(set(pruned_load_domain_for_pallet))

    return domains

#Helper parse variable from the variable dict given in define variables. this allows us to easily differentiate when we get to the constraints
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

# The constraint checker
#Next is the constraint checker which will be extremely important as it will be pretty much called every time something is passed through the main alg
#idea is the checker will take a variable such as Plane1_Hangar-Arrival_Time, a value from that vars domain so like one of the possible times 800
#the assigmnets which are the approved actions so far in the schdule which will compare for conflicts with those, and the problem data so like the general data from JSON
# I had a bit of trouble understanding how  this function would be structured when i made my first attempt. So what I used a blueprint from geeksforgeeks
#https://www.geeksforgeeks.org/artificial-intelligence/constraint-satisfaction-problems-csp-in-artificial-intelligence/
# but rather than having constraints be their own separate thing, i ended up putting them all in one function. Later when we revamped our vars, i then sectioned the 
#constraint out in terms of which variable they appplied to 

def meets_constraints(variable, value, assignments, problem_data):
   
    
    # If a variable is unassigned in the current branch, it's not a violation yet.
    if value is None:
        return True

    info = parse_variable(variable)
    stop_time = problem_data['meta']['Stop Time']

    #Constraits for 'Plane_Arrival' 
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
                    #first staright up check arrival overlap
                    if assigned_time == other_time:
                        return False
                    
                    #if goes into the other time
                    if assigned_time < convert_time(other_time + 20):
                        return False
                    
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
                            unload_finish = convert_time(unload_start + PLANE_UNLOAD_TIME)
                            if unload_finish > other_departure_time:
                                other_departure_time = unload_finish
                    
                    # if other_departure_time == other_time:
                    #     other_departure_time = convert_time(other_departure_time + PLANE_UNLOAD_TIME)
                    
                    if assigned_time < other_departure_time:
                        return False 

    # Constraints for 'Pallet_Assignment' 
    elif info['type'] == 'Pallet_Assignment':
        assigned_truck = value
        
        # Rule: "Each cargo truck can receive one pallet."
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue

            if 'Pallet_Assignment' in other_var and other_val == assigned_truck:
                return False 
    
    #Constraints for 'Unload_Task' 
    elif info['type'] == 'Unload_Task':
        assigned_forklift, unload_start_time = value

        # Rule: Unloading must finish by the stop time.
        if convert_time(unload_start_time + PLANE_UNLOAD_TIME) > stop_time:
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
        
        # Rule: This unload task cannot conflict with OTHER plane arrivals in the same hangar.
        for other_var, other_val in assignments.items():
            if other_val is None or 'Plane_Arrival' not in other_var:
                continue
            
            # Don't check against our own plane
            if other_var == plane_arrival_var:
                continue

            other_plane_hangar, other_plane_arrival_time = other_val
            
            # If another plane is in the same hangar...
            if other_plane_hangar == hangar:
                # Get the other plane's *minimum* interval
                other_start = other_plane_arrival_time
                other_end = convert_time(other_plane_arrival_time + PLANE_UNLOAD_TIME)
                
                # Get this task's interval
                task_start = unload_start_time
                task_end = convert_time(unload_start_time + PLANE_UNLOAD_TIME)
                
                # Check if this task overlaps with that plane's minimum occupancy
                if max(task_start, other_start) < min(task_end, other_end):
                    return False 
        
        # Rule: A forklift can only do one thing at a time.
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue
            
            if 'Unload_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                    # Check for time overlap
                    if max(unload_start_time, other_start_time) < min(convert_time(unload_start_time + PLANE_UNLOAD_TIME), convert_time(other_start_time + PLANE_UNLOAD_TIME)):
                        return False 
            
            if 'Load_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                     if max(unload_start_time, other_start_time) < min(convert_time(unload_start_time + PLANE_UNLOAD_TIME), convert_time(other_start_time + TRUCK_LOAD_TIME)):
                        return False
                    
    #constraint for 'Truck_Hangar_Arrival' 
    if info['type'] == 'Truck_Hangar':
        assigned_hangar, arrival_time = value
        departure_time = convert_time(arrival_time + TRUCK_LOAD_TIME)

        # Rule: "Each hangar can accommodate one truck at any given time."
        for other_var, other_val in assignments.items():
            if other_val is None or other_var == variable:
                continue
            
            if 'Truck_Hangar_Arrival' in other_var:
                other_hangar, other_arrival = other_val
                if assigned_hangar == other_hangar:
                    other_departure = convert_time(other_arrival + TRUCK_LOAD_TIME)
                    # Check for time overlap
                    if max(arrival_time, other_arrival) < min(departure_time, other_departure):
                        return False

    # constraints for 'Load_Task' 
    elif info['type'] == 'Load_Task':
        assigned_forklift, load_start_time = value

        # Rule: Loading must finish by the stop time.
        if convert_time(load_start_time + TRUCK_LOAD_TIME) > stop_time:
            return False
        
        # Rule: Loading must happen after the pallet has been unloaded.
        unload_task_var = f"Unload_Task_{info['pallet_id']}"
        unload_task_val = assignments.get(unload_task_var)
        if not unload_task_val:
            return False 

        forklift, unload_start_time = unload_task_val
        unload_finish_time = convert_time(unload_start_time + PLANE_UNLOAD_TIME)
        # Trying to load before unloading is finished.
        if load_start_time < unload_finish_time:
            return False 

        # Rule: A forklift can only load if there is a truck there
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
                    if max(load_start_time, other_start_time) < min(convert_time(load_start_time + TRUCK_LOAD_TIME), convert_time(other_start_time + PLANE_UNLOAD_TIME)):
                        return False
            
            if 'Load_Task' in other_var:
                other_forklift, other_start_time = other_val
                if assigned_forklift == other_forklift:
                     if max(load_start_time, other_start_time) < min(convert_time(load_start_time + TRUCK_LOAD_TIME), convert_time(other_start_time + TRUCK_LOAD_TIME)):
                        return False

    return True

# def check_constraint(var1, value1, var2, value2):
#     value1 = value1[1] if isinstance(value1, tuple) else value1
#     value2 = value2[1] if isinstance(value2, tuple) else value2

#     # Plane must arrive before unloading starts
#     if "Plane_Arrival" in var1 and "Unload_Task" in var2:
#         return value2 >= value1

#     # Unloading must finish before loading begins
#     if "Unload_Task" in var1 and "Load_Task" in var2:
#         return value2 >= value1 + PLANE_UNLOAD_TIME

#     # Truck must arrive before loading begins
#     if "Truck_Hangar_Arrival" in var1 and "Load_Task" in var2:
#         return value2 >= value1

#     return True


# CONSTRAINT_RULES = {
#     "Load_Task": ["Truck_Hangar_Arrival"],     # Loading depends on truck arrival
#     "Unload_Task": ["Plane_Arrival"],          # Unloading depends on plane arrival
#     "Pallet_Assignment": ["Truck_Hangar_Arrival"],  # Which truck handles which pallet
# }


# def build_constraint_graph(variables):
#     graph = {}

#     for var1 in variables:
#         for var2 in variables:
#             if var1 == var2:
#                 continue

#             # If the two variables are dependent on each other, add an edge to constraint graph
#             for key, targets in CONSTRAINT_RULES.items():
#                 if key in var1:
#                     for target in targets:
#                         if target in var2:
#                             graph.setdefault(var1, []).append(var2)
#                             graph.setdefault(var2, []).append(var1)

#     return graph

# def revise(domains, xi, xj, inferences):
#     revised = False

#     # Clone xi domain to iterate while modifying
#     for x in domains[xi][:]:
#         if not any(check_constraint(xi, x, xj, y) for y in domains[xj]):
#             domains[xi].remove(x)
#             inferences.append((xi, x))
#             revised = True

#     return revised


# def ac3(domains, constraints, queue = None):
#     if queue is None:
#         queue = [(xi, xj) for xj in constraints.get(xi, [])]
        
#     inferences = []

#     while queue:
#         xi, xj = queue.pop(0)

#         # If the domain was revised
#         if revise(domains, xi, xj, inferences):
#             # If a domain ends up empty, return failure
#             if not domains[xi]:
#                 return None

#             # Add neighboring constraints into the queue
#             for xk in constraints.get(xi, []):
#                 if xk != xj:
#                     queue.append((xk, xi))

#     return inferences


# def restore_inferences(domains, inferences):
#     for var, value in inferences:
#         if value not in domains[var]:
#             domains[var].append(value)


# def termination_condition(assignments, problem_data):
#     # Terminate when all aircraft cargo loads have been completed
#     loaded = set()
#     for assignment in assignments.keys():
#         if assignment.startswith('Load_Pallet_'):
#             loaded.add(assignment.split('_')[2])

#     total_cargo = sum(data['Cargo'] for data in problem_data['aircraft'].values())
#     return len(loaded) == total_cargo


#we tried to do AC3 to speed up time but ended up settling by instead just pruning the domain to have less value options to run through, this ended up saving us the time
#a link I referenced for the AC3 came from berkeley https://inst.eecs.berkeley.edu/~cs188/textbook/csp/filtering.html
def solve_csp(assignments, variables, domains, problem_data):
    # Base Case: If the list of variables to process is empty, we have a complete solution.
    if not variables:
        return assignments

    variable = variables[0]
    # Iterate through all possible values in the domain for this variable.
    for value in domains[variable]:
        # assign the value.
        assignments[variable] = value
        # Check if this assignment is consistent with all constraints
        if meets_constraints(variable, value, assignments, problem_data):   
            #if yea keep going
            result = solve_csp(assignments, variables[1:], domains, problem_data)
            #Return if solution
            if result is not None:
                return result
        #If the assignment didnt work or the recursion cooked, backtrack.
        del assignments[variable]

    #If after every solution we got nothing then means no solution so return nothing
    return None


# The output formatter
#writing into a json file in python is something pretty foreign to me so i had to utilize outside resources from google to understand how to get it in the 
#format I was looking for. the biggest help was this geeks for geeks website https://www.geeksforgeeks.org/python/reading-and-writing-json-to-a-file-in-python/
#which actually had a close to ideal template for me to use for the formatter.
def format_solution(solution, problem_data):
    schedule = {
        "aircraft": {},
        "trucks": {},
        "forklifts": {fork: [] for fork in problem_data['meta']['Forklifts']}
    }
    
    plane_to_hangar = {}
    for var, val in solution.items():
        if val is None: continue
        if 'Plane_Arrival' in var:
            info = parse_variable(var)
            plane = info['plane']
            hangar = val[0] 
            plane_to_hangar[plane] = hangar
            
    for var, val in solution.items():
        
        info = parse_variable(var)
        
        # Aircraft
        if info['type'] == 'Plane_Arrival':
            plane = info['plane']
            hangar, arrival_time = val
            
            # we dont have a departure time variable right ok
            #no, so im g onna calc based on the end of the last unload time for that plane
            departure_time = arrival_time
            #this val will get updated ^
            for p_var, p_val in solution.items():
                if p_val and f"Unload_Task_{plane}_Pallet" in p_var:
                    unload_finish = convert_time(p_val[1] + PLANE_UNLOAD_TIME)
                    if unload_finish > departure_time:
                        departure_time = unload_finish 
                        
            schedule['aircraft'][plane] = {
                "Hangar": hangar,
                "Arrival": arrival_time,
                "Departure": departure_time
            }
        
        # truck
        elif info['type'] == 'Truck_Hangar':
            truck = info['truck']
            hangar, arrival_time = val
            
            schedule['trucks'][truck] = {
                "Hangar": hangar,
                "Arrival": arrival_time,
                "Departure": convert_time(arrival_time + TRUCK_LOAD_TIME)
            }
            
        # Forks
        elif info['type'] in ['Unload_Task', 'Load_Task']:
            forklift, start_time = val
            if info['type'] == 'Unload_Task':
                job_type = "Unload" 
            else:
                job_type = "Load"
            
            # Find the hangar this task happened in
            plane = info['plane']
            hangar = plane_to_hangar.get(plane)
            
            job = {
                "Hangar": hangar,
                "Time": start_time,
                "Job": job_type
            }
            schedule['forklifts'][forklift].append(job)

    for fork in schedule['forklifts']:
        schedule['forklifts'][fork].sort(key=lambda job: job['Time'])
        
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
        print("No file")
        sys.exit(1)

    all_variables = define_variables(meta_data, aircraft_data, truck_data)
    domains = define_domains(meta_data, aircraft_data, truck_data)
    # print(all_variables)
    
    #in order to speed up the time, we want to minimize the time till failure so we dont go far and have to go all the way back
    #so this reorders the variables in a way that will do so
    def sort_key(variable_name):
        if 'Plane_Arrival' in variable_name:
            return 0  
        if 'Unload_Task' in variable_name:
            return 1  
        if 'Pallet_Assignment' in variable_name:
            return 2  
        if 'Load_Task' in variable_name:
            return 4  
        if 'Truck_Hangar_Arrival' in variable_name:
            return 3  
        return 5

    all_variables.sort(key=sort_key)
    # print("-----------------------------------NEW VARIABLE SORT --------------------------------------------")
    # print(all_variables)
    
    #problem_data["constraints"] = build_constraint_graph(all_variables)
    solution = solve_csp({}, all_variables, domains, problem_data)

    if solution is not None:
        # print("-----------------------------------Solution--------------------------------------------")
        # print(solution)
        # print("Solution found!")
        schedule_output = format_solution(solution, problem_data)
    else:
        # print("No solution found for this problem, this airport sucks IAD better")
        schedule_output = {
            "aircraft": None,
            "trucks": None,
            "forklifts": None
        }
    
    #Print to the file 
    try:
        with open(schedule_path, 'w') as f:
            json.dump(schedule_output, f, indent=4)
        #print(f"Schedule successfully written to {schedule_path}")
    except IOError as e:
        #print(f"Error writing to file: {e}")
        sys.exit(1)