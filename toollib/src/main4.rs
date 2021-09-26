// 测试概率计算
mod utils;
use utils::{
    cal3BV, calOp, enuOneStep, layMineNumber, layMineOpNumber, refreshBoard,
    unsolvableStructure
};
mod algorithms;
use algorithms::{
    isSolvable, layMineOp, layMineSolvable_thread, SolveDirect, SolveEnumerate, cal_possibility,
    SolveMinus, layMine, layMineSolvable, sample_3BVs_exp, OBR_board, mark_board, cal_possibility_onboard,
};
mod OBR;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use rand::seq::SliceRandom;
use rand::thread_rng;
// use pyo3::PyTraverseError;
use itertools::Itertools;
use pyo3::class::basic::PyObjectProtocol;
use std::cmp::max;
use std::cmp::min;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread;


#[derive(Clone, Debug)]
struct big_number {
    // 科学计数法表示的大数字
    // 必定大于等于1，a必定满足小于10大于等于1
    a: f64,
    b: i32,
}

impl big_number {
    fn a_become_smaller_than(&mut self, thrd: f64) {
        // 如果big_number大于thrd
        // 把位数都放到指数上，使其满足a小于10大于等于1
        if self.a < thrd {
            return;
        }
        while self.a >= 10.0 {
            self.a /= 10.0;
            self.b += 1;
        }
    }
    fn mul_usize(&mut self, k: usize) {
        // 与usize相乘
        if k == 0 {
            self.a = 0.0;
            self.b = 1;
        } else {
            self.a *= k as f64;
            self.a_become_smaller_than(10.0);
        }
    }
    fn mul_big_number(&mut self, k: &big_number) {
        // 与big_number相乘, big_number必须至少为1
        self.a *= k.a;
        self.b += k.b;
        self.a_become_smaller_than(10.0);
    }
    fn add_big_number(&mut self, k: &big_number) {
        let mut ka = k.a;
        let mut kb = k.b;
        while self.b > kb {
            ka /= 10.0;
            kb += 1;
        }
        while self.b < kb {
            self.a /= 10.0;
            self.b += 1;
        }
        self.a += ka;
        self.a_become_smaller_than(10.0);
    }
    fn div_big_num(&self, k: &big_number) -> f64 {
        // 计算大数相除
        let mut ans = self.a / k.a;
        let mut b = self.b;
        while b < k.b {
            ans /= 10.0;
            b += 1;
        }
        while b > k.b {
            ans *= 10.0;
            b -= 1;
        }
        ans
    }
    fn div_usize(&mut self, k: usize) {
        // 计算大数除以正整数。这里被除数大于等于0；除数大于等于1
        if self.a < 1e-8 && self.b == 1 {
            return;
        } else {
            self.a /= k as f64;
            while self.a < 1.0 {
                self.a *= 10.0;
                self.b -= 1;
            }
        }
    }
}

fn C(n: usize, k: usize) -> big_number {
    // n不超过1e10
    if n < k + k {
        return C(n, n - k);
    };
    let maximum_limit: f64 = 1e208;
    let mut c = big_number { a: 1.0, b: 0 };
    for i in 0..k {
        c.a *= (n - i) as f64;
        c.a /= (i + 1) as f64;
        c.a_become_smaller_than(maximum_limit);
    }
    c.a_become_smaller_than(10.0);
    c
}

fn C_usize(n: usize, k: usize) -> usize {
    // 小数字的组合数计算
    if n < k + k {
        return C_usize(n, n - k);
    };
    let mut c = 1;
    for i in 0..k {
        c *= n - i;
    }
    for i in 0..k {
        c /= i + 1;
    }
    c
}

fn combine(
    MatrixA: Vec<Vec<i32>>,
    Matrixx: Vec<(usize, usize)>,
) -> (Vec<Vec<i32>>, Vec<(usize, usize)>, Vec<Vec<usize>>) {
    // 检查地位完全相同的格子，全部返回。例如[[3,1,2],[0,5],[4],[6]]
    // MatrixA不能为空
    // 并在内部更改矩阵，合并重复的列
    let mut matrixA_squeeze = MatrixA;
    let mut matrixx_squeeze = Matrixx;
    let mut pair_cells = vec![];
    let mut del_cells = vec![]; // 由于重复需要最后被删除的列
    for i in 0..matrixx_squeeze.len() {
        pair_cells.push(vec![i]);
        for j in i + 1..matrixA_squeeze[0].len() {
            if !matrixA_squeeze.iter().any(|x| x[i] != x[j]) {
                pair_cells[i].push(j);
                del_cells.push(j);
            }
        }
    }
    del_cells.sort_by(|a, b| b.cmp(&a));
    del_cells.dedup();
    for i in del_cells {
        for r in 0..matrixA_squeeze.len() {
            matrixA_squeeze[r].remove(i);
        }
        matrixx_squeeze.remove(i);
        pair_cells.remove(i);
    }
    let cell_squeeze_num = pair_cells.len();
    for i in 0..cell_squeeze_num {
        let k = pair_cells[i].len() as i32;
        for r in 0..matrixA_squeeze.len() {
            matrixA_squeeze[r][i] *= k;
        }
    }
    (matrixA_squeeze, matrixx_squeeze, pair_cells)
}

fn enum_comb(
    matrixA_squeeze: &Vec<Vec<i32>>,
    matrixx_squeeze: &Vec<(usize, usize)>,
    Matrixb: &Vec<i32>,
) -> Vec<Vec<usize>> {
    // 暴力枚举，返回一个包含所有情况的表，无任何优化
    // matrixA_squeeze包含0，1，2，3等，代表是几个格子压缩为一个
    let Column = matrixx_squeeze.len();
    let Row = matrixA_squeeze.len();
    let mut enum_comb_table = vec![vec![0; Column]];
    let mut not_enum_cell: Vec<bool> = vec![true; Column]; // 记录每个位置是否被枚举过，true是没有被枚举过
    let mut enum_cell_table: Vec<Vec<usize>> = vec![];
    for row in 0..Row {
        let mut new_enum_cell = vec![]; // 当前条件涉及的新格子
        let mut enum_cell = vec![]; // 当前条件涉及的所有格子
        let mut new_enum_max = vec![];
        for j in 0..Column {
            if matrixA_squeeze[row][j] > 0 {
                enum_cell.push(j);
                if not_enum_cell[j] {
                    not_enum_cell[j] = false;
                    new_enum_cell.push(j);
                    new_enum_max.push(matrixA_squeeze[row][j]);
                }
            }
        }
        // 第一步，整理出当前条件涉及的所有格子，以及其中哪些是新格子
        let mut new_enum_table = (0..new_enum_cell.len())
            .map(|i| 0..new_enum_max[i] + 1)
            .multi_cartesian_product()
            .collect::<Vec<_>>();
        new_enum_table.retain(|x| x.iter().sum::<i32>() <= Matrixb[row]);
        // println!("{:?}", new_enum_table);
        // 第二步，获取这些新枚举到的格子的所有满足周围雷数约束的情况，即子枚举表
        if new_enum_table.is_empty() {
            enum_comb_table.retain(|item| {
                enum_cell
                    .iter()
                    .fold(0, |sum: usize, i: &usize| sum + item[*i])
                    == Matrixb[row] as usize
            });
        // 第三步，若子枚举表为空，不用将子枚举表与主枚举表合并；且只检查主枚举表是否满足当前这条规则，删除一些不满足的
        } else {
            let mut flag_1 = true; // 代表新枚举的格子是否需要新增情况
            let enum_comb_table_len = enum_comb_table.len();
            for item in new_enum_table {
                if flag_1 {
                    for m in 0..new_enum_cell.len() {
                        for n in 0..enum_comb_table_len {
                            enum_comb_table[n][new_enum_cell[m]] = item[m] as usize;
                        }
                    }
                    flag_1 = false;
                } else {
                    for n in 0..enum_comb_table_len {
                        let mut one_row_in_new_table = enum_comb_table[n].clone();
                        for m in 0..new_enum_cell.len() {
                            one_row_in_new_table[new_enum_cell[m]] = item[m] as usize;
                        }
                        enum_comb_table.push(one_row_in_new_table);
                    }
                }
            } // 第四步，若子枚举表非空，先将子枚举表与主枚举表合并
            let mut equations = vec![];
            for kk in &enum_cell {
                for rr in 0..row {
                    if matrixA_squeeze[rr][*kk] > 0 {
                        equations.push(rr);
                    }
                }
            }
            equations.dedup();
            // 第五步，再找出本条规则涉及的之前所有的规则的id
            for equ in equations {
                enum_comb_table.retain(|item| {
                    enum_cell_table[equ]
                        .iter()
                        .fold(0, |sum: usize, i: &usize| sum + item[*i])
                        == Matrixb[equ] as usize
                });
            }
            enum_comb_table.retain(|item| {
                enum_cell
                    .iter()
                    .fold(0, |sum: usize, i: &usize| sum + item[*i])
                    == Matrixb[row] as usize
            }); // 这段重复了，不过不影响性能，之后优化
                // 第六步，用本条规则、以及涉及的之前所有规则过滤所有情况
        }
        enum_cell_table.push(enum_cell);
    }
    enum_comb_table
}

pub fn refresh_matrixs(
    board_of_game: &Vec<Vec<i32>>,
) -> (
    Vec<Vec<Vec<i32>>>,
    Vec<Vec<(usize, usize)>>,
    Vec<Vec<i32>>,
    usize,
    usize,
) {
    // 根据游戏局面分块生成矩阵。分块的数据结构是最外面再套一层Vec
    // board_of_game必须且肯定是正确标雷的游戏局面，但不需要标全
    // 矩阵的行和列都可能有重复
    // unknow_block是未知格子数量, is_mine_num是标出的是雷的数量
    let Row = board_of_game.len();
    let Column = board_of_game[0].len();
    let mut unknow_block = 0;
    let mut is_mine_num = 0;
    let mut matrix_as = vec![];
    let mut matrix_xs = vec![];
    let mut matrix_bs = vec![];
    let mut all_cell: Vec<(usize, usize)> = vec![]; // 记录所有周围有未打开格子的数字的位置
    for i in 0..Row {
        for j in 0..Column {
            if board_of_game[i][j] > 0 && board_of_game[i][j] < 10 {
                'outer: for m in max(1, i) - 1..min(Row, i + 2) {
                    for n in max(1, j) - 1..min(Column, j + 2) {
                        if board_of_game[m][n] == 10 {
                            all_cell.push((i, j));
                            break 'outer;
                        }
                    }
                }
            } else if board_of_game[i][j] == 10 {
                // 数内部有几个格子
                let mut flag = true;
                for m in max(1, i) - 1..min(Row, i + 2) {
                    for n in max(1, j) - 1..min(Column, j + 2) {
                        if board_of_game[m][n] < 10 {
                            flag = false;
                        }
                    }
                }
                if flag {
                    unknow_block += 1;
                }
            } else if board_of_game[i][j] == 11 {
                is_mine_num += 1;
            }
        }
    }
    let mut p = 0; //指针，代表第几块
    // println!("{:?}", all_cell);
    while !all_cell.is_empty() {
        matrix_xs.push(vec![]);
        matrix_bs.push(vec![]);
        let x_0 = all_cell[0].0;
        let y_0 = all_cell[0].1;
        let mut num_cells = vec![]; // 记录了当前块的数字格的坐标
        let mut temp_cells = vec![]; // 记录了待查找的数字格的坐标
        let mut flag_num = 0;
        for m in max(1, x_0) - 1..min(Row, x_0 + 2) {
            for n in max(1, y_0) - 1..min(Column, y_0 + 2) {
                if board_of_game[m][n] == 10 {
                    matrix_xs[p].push((m, n));
                }
                if board_of_game[m][n] == 11 {
                    flag_num += 1;
                }
            }
        }
        matrix_bs[p].push(board_of_game[x_0][y_0] - flag_num);
        num_cells.push((x_0, y_0));
        temp_cells.push((x_0, y_0));
        while !temp_cells.is_empty() {
            let x_e = temp_cells[0].0;
            let y_e = temp_cells[0].1;
            temp_cells.remove(0);
            for t in (1..all_cell.len()).rev() {
                // 从temp_cells中拿出一个格子，找出与其相邻的所有格子，加入temp_cells和matrix_bs、matrix_xs
                let x_t = all_cell[t].0;
                let y_t = all_cell[t].1;
                if x_t >= x_e + 3 || x_e >= x_t + 3 || y_t >= y_e + 3 || y_e >= y_t + 3 {
                    continue;
                }
                let mut flag_be_neighbor = false;
                for m in max(1, max(x_t, x_e)) - 1..min(Row, min(x_t + 2, x_e + 2)) {
                    for n in max(1, max(y_t, y_e)) - 1..min(Column, min(y_t + 2, y_e + 2)) {
                        if board_of_game[m][n] == 10 {
                            flag_be_neighbor = true;
                            break;
                        }
                    }
                } // 从局面上看，如果两个数字有相同的未知格子，那么就会分到同一块
                if flag_be_neighbor {
                    let mut flag_num = 0;
                    for m in max(1, x_t) - 1..min(Row, x_t + 2) {
                        for n in max(1, y_t) - 1..min(Column, y_t + 2) {
                            if board_of_game[m][n] == 10 {
                                if !matrix_xs[p].iter().any(|x| x.0 == m && x.1 == n) {
                                    matrix_xs[p].push((m, n));
                                }
                            }
                            if board_of_game[m][n] == 11 {
                                flag_num += 1;
                            }
                        }
                    }
                    matrix_bs[p].push(board_of_game[x_t][y_t] - flag_num);
                    num_cells.push((x_t, y_t));
                    temp_cells.push(all_cell[t]);
                    all_cell.remove(t);
                }
            }
        }
        matrix_as.push(vec![vec![0; matrix_xs[p].len()]; matrix_bs[p].len()]);
        for i in 0..num_cells.len() {
            for j in 0..matrix_xs[p].len() {
                if num_cells[i].0 <= matrix_xs[p][j].0 + 1
                    && matrix_xs[p][j].0 <= num_cells[i].0 + 1
                    && num_cells[i].1 <= matrix_xs[p][j].1 + 1
                    && matrix_xs[p][j].1 <= num_cells[i].1 + 1
                {
                    matrix_as[p][i][j] = 1;
                }
            }
        }
        all_cell.remove(0);
        p += 1;
    }
    (matrix_as, matrix_xs, matrix_bs, unknow_block, is_mine_num)
}

fn enum_count(
    matrixA_squeeze: &Vec<Vec<i32>>,
    matrixx_squeeze: &Vec<(usize, usize)>,
    matrix_b: &Vec<i32>,
    combination_relationship: &Vec<Vec<usize>>) -> Result<([Vec<usize>; 2], Vec<Vec<usize>>), usize>{
    // 枚举并统计，得到每块雷数分布表和每块每格雷数表，顺便计算最小、最大雷数
    let mut table_minenum: [Vec<usize>; 2] = [vec![], vec![]];
    // 每块雷数分布表：记录了每块（不包括内部块）每种总雷数下的是雷总情况数
    // 例如：[[17, 18, 19, 20, 21, 22, 23, 24], [48, 2144, 16872, 49568, 68975, 48960, 16608, 2046]]
    let mut table_cell_minenum: Vec<Vec<usize>> = vec![];
    // 每块每格雷数表：记录了每块每格（或者地位等同的复合格）、每种总雷数下的是雷情况数

    if matrixx_squeeze.len() > 45 {
        // 超出枚举极限长度
        return Err(0)
    }
    let enum_comb_table = enum_comb(&matrixA_squeeze, &matrixx_squeeze, &matrix_b);
    if enum_comb_table.len() == 0 {
        // 无解局面
        return Err(1)
    }
    for s in enum_comb_table.clone() {
        // println!("s: {:?}", s);
        let s_sum = s.iter().sum::<usize>();
        let mut si_num = 1; // 由于enum_comb_table中的格子每一个都代表了与其地位等同的所有格子，由此的情况数
        for s_i in 0..s.len() {
            si_num *= C_usize(combination_relationship[s_i].len(), s[s_i]);
        }
        // println!("si_num = {:?}", si_num);
        let fs = table_minenum[0].clone().iter().position(|x| *x == s_sum);
        // println!("table_minenum = {:?}", table_minenum);
        // println!("fs = {:?}", fs);
        match fs {
            None => {
                table_minenum[0].push(s_sum);
                table_minenum[1].push(si_num);
                let mut ss = vec![];
                for c in 0..s.len() {
                    if s[c] == 0 {
                        ss.push(0);
                    } else {
                        let mut sss = 1;
                        for d in 0..s.len() {
                            if c != d {
                                sss *= C_usize(combination_relationship[d].len(), s[d]);
                                // println!("comb_relp_s = {:?}", comb_relp_s);
                                // println!("sss = {:?}", sss);
                            } else {
                                sss *= C_usize(combination_relationship[d].len() - 1, s[d] - 1);
                            }
                        }
                        ss.push(sss);
                    }
                }
                table_cell_minenum.push(ss);
                // println!("table_minenum: {:?}", table_minenum);
                // println!("table_cell_minenum:{:?}", table_cell_minenum);
            }
            _ => {
                table_minenum[1][fs.unwrap()] += si_num;
                for c in 0..s.len() {
                    if s[c] == 0 {
                        continue;
                    } else {
                        let mut sss = 1;
                        for d in 0..s.len() {
                            if c != d {
                                sss *= C_usize(combination_relationship[d].len(), s[d]);
                                // println!("comb_relp_s=={:?}", comb_relp_s);
                                // println!("s=={:?}", s);
                            } else {
                                sss *= C_usize(combination_relationship[d].len() - 1, s[d] - 1);
                            }
                        }
                        table_cell_minenum[fs.unwrap()][c] += sss;
                    }
                }
            }
        }
    }

    Ok((table_minenum, table_cell_minenum))
}

fn main() {
    // println!("执行main");
    // let game_board = vec![
    //     vec![ 1, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![ 1, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![ 2, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10],
    // ];
    let game_board = vec![
        vec![10, 10, 2, 2, 10, 10],
        vec![10, 10, 10, 2, 2, 2],
        vec![10, 10, 4, 3, 1, 0],
        vec![10, 10, 10, 10, 3, 1],
        vec![2, 10, 4, 10, 10, 1],
        vec![1, 1, 2, 2, 2, 1],
    ];
    // let ans = cal_possibility(&game_board, 10);

    // let game_board = vec![
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 2, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 5, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    // ];
    // let ans = cal_possibility(&game_board, 10);

    // let game_board = vec![
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 1, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 1, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    // ];
    // let ans = cal_possibility(&game_board, 10);

    // let game_board = vec![
    //     vec![ 0,  0,  1, 10, 10, 10, 10, 10],
    //     vec![ 0,  1,  2, 10, 10, 10, 10, 10],
    //     vec![ 0,  2, 11, 12, 10, 10, 10, 10],
    //     vec![ 0,  3, 10, 10, 10, 12, 10, 10],
    //     vec![ 0,  3, 10,  4,  2, 10, 10, 10],
    //     vec![ 0,  3, 10,  3,  2, 11, 10, 10],
    //     vec![ 0,  2, 11,  2,  2, 10, 10, 10],
    //     vec![ 0,  1,  1,  1,  1, 10, 10, 10],
    // ];
    // let ans = cal_possibility(&game_board, 10);

    // let game_board = vec![
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 2, 1, 1, 2, 1, 1, 1, 10, 10, 3, 2, 3, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 2, 1, 0, 0, 0, 0, 0, 1, 3, 3, 2, 0, 1, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 1, 0, 0, 0, 1, 1, 1, 0, 1, 10, 1, 1, 1, 1, 1, 2, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 2, 1, 1, 0, 1, 10, 1, 0, 1, 1, 2, 2, 10, 1, 0, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 1, 0, 2, 2, 2, 1, 1, 1, 1, 10, 3, 2, 0, 1, 3, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 2, 1, 2, 10, 2, 1, 10, 1, 2, 3, 10, 1, 0, 0, 2, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 3, 3, 2, 2, 1, 10, 10, 1, 0, 0, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 3, 10, 1, 1, 1, 2, 1, 1, 0, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 2, 0, 0, 1, 10, 1, 1, 2, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 2, 0, 0, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 2, 1, 2, 2, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    // ];
    // let game_board = vec![
    //     vec![2, 10, 3, 10, 3, 10, 3, 10, 3, 10, 3, 10, 3, 10, 3, 10, 3, 10, 3, 10, 1],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![3, 10, 4, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10], 
    //     vec![10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
    // ];
    let mut game_board = game_board.clone();
    mark_board(&mut game_board);
    // println!("{:?}", game_board);
    // let (mut MatrixA, mut Matrixx, mut Matrixb, _) = refresh_matrixs(&game_board);
    // println!("{:?}", MatrixA);
    // println!("{:?}", Matrixx);
    // println!("{:?}", Matrixb);
    let ans = cal_possibility(&game_board, 0.334);
    println!("{:?}", ans);

    // let game_board = vec![
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10,  3, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    //     vec![10, 10, 10, 10, 10, 10, 10, 10],
    // ];
    // let ans = cal_possibility(&game_board, 10);

    // let game_board = vec![
    //     vec![ 0,  0, 11, 10, 10, 11,  0,  0],
    //     vec![ 0,  0, 11,  4,  4, 11,  0,  0],
    //     vec![ 0,  0, 11,  0,  0, 11,  0,  0],
    //     vec![ 0,  0,  0,  0,  0,  0,  0,  0],
    //     vec![ 0,  0,  0,  0,  0,  0,  0,  0],
    //     vec![ 0,  0, 11,  0,  0, 11,  0,  0],
    //     vec![ 0,  0, 11,  4,  4, 11,  0,  0],
    //     vec![ 0,  0, 11, 10, 10, 11,  0,  0],
    // ];
    // let ans = cal_possibility(&game_board, 2);

    // let game_board = vec![
    //     vec![11, 2, 2, 11, 1, 1, 10],
    //     vec![2, 10, 10, 3, 2, 2, 10],
    //     vec![1, 10, 10, 10, 10, 10, 10],
    // ];
    // let ans = cal_possibility(&game_board, 5);

    // println!("{:?}", ans.0);
    // println!("{:?}", ans.1);

}