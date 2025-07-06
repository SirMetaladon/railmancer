grid = [[1], [2], [3]], [[4], [5], [6]], [[7], [8], [9]]

link = grid[0][0]
grid[0][1] = link

grid[0][2] = grid[0][1]
grid[0][1][0] = 99

print(grid[0])
